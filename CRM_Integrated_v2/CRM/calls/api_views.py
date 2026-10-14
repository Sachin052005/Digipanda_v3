"""
REST API for the CRM Call Sync Android app (unchanged paths and payloads, so app v1.1+ works as-is):

    POST /api/auth/token/             username + password -> {"token", "name"}
    POST /api/calls/ingest/           {"calls": [{number, call_type, timestamp_ms, duration_sec, sim_account_id, contact_name}]}
    POST /api/call-recordings/upload/ multipart: audio_file, device_file_id, phone_number, direction,
                                      duration_seconds, call_started_at
"""
from django.contrib.auth import authenticate
from rest_framework import status
from rest_framework.authentication import TokenAuthentication
from rest_framework.authtoken.models import Token
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny, BasePermission, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from rest_framework.views import APIView

from . import sync_services as services

MAX_CALLS_PER_REQUEST = 500


def _app_meta(request):
    """Optional headers the app sends: X-App-Version, X-Google-Sim."""
    return {
        "app_version": request.headers.get("X-App-Version", ""),
        "google_sim": request.headers.get("X-Google-Sim"),
    }


class LoginThrottle(AnonRateThrottle):
    rate = "10/min"


class AppLoginView(APIView):
    """POST username + password -> {"token": ..., "name": ...} for the CRM Call Sync app."""

    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [LoginThrottle]
    parser_classes = [FormParser, MultiPartParser, JSONParser]

    def post(self, request):
        username = str(request.data.get("username", "")).strip()
        password = str(request.data.get("password", ""))
        user = authenticate(request, username=username, password=password)
        if user is None or not user.is_active:
            return Response({"error": "Wrong username or password"}, status=status.HTTP_400_BAD_REQUEST)
        if not services.can_use_app(user):
            return Response(
                {"error": "This login can't use the call sync app. Use your CRM Telecaller login "
                          "(or ask your admin to check your role)."},
                status=status.HTTP_403_FORBIDDEN,
            )
        token, _ = Token.objects.get_or_create(user=user)
        services.device_for_user(user, **_app_meta(request))
        return Response({"token": token.key, "name": services.display_name(user)})


class AppTokenAuthentication(TokenAuthentication):
    """Token auth that always answers 401 (never 403) so the app knows to log in again."""

    def authenticate_credentials(self, key):
        user, token = super().authenticate_credentials(key)
        if not services.can_use_app(user):
            raise AuthenticationFailed("This login can no longer use the call sync app.")
        return user, token


class IsAppUser(BasePermission):
    def has_permission(self, request, view):
        return services.can_use_app(request.user)


class AppAPIView(APIView):
    authentication_classes = [AppTokenAuthentication]
    permission_classes = [IsAuthenticated, IsAppUser]


class CallIngestView(AppAPIView):
    """Google-number calls from the phone's call log: {"calls": [...]}."""

    parser_classes = [JSONParser]

    def post(self, request):
        calls = request.data.get("calls") if isinstance(request.data, dict) else None
        if not isinstance(calls, list):
            return Response({"error": 'body must be JSON: {"calls": [...]}'}, status=status.HTTP_400_BAD_REQUEST)
        if len(calls) > MAX_CALLS_PER_REQUEST:
            return Response({"error": f"max {MAX_CALLS_PER_REQUEST} calls per request"},
                            status=status.HTTP_400_BAD_REQUEST)
        device = services.device_for_user(request.user, **_app_meta(request))
        return Response(services.ingest_calls(device, calls))


class RecordingUploadView(AppAPIView):
    """Multipart upload from the app: audio_file + device_file_id, phone_number, direction, ..."""

    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        device = services.device_for_user(request.user, **_app_meta(request))
        try:
            rec, created = services.save_recording(device, request.FILES.get("audio_file"), request.data)
        except services.RecordingRejected as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            {"id": rec.pk, "duplicate": not created, "lead_id": rec.lead_id,
             "call_event_id": rec.call_event_id, "call_history_id": rec.call_history_id},
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class PendingCallDialView(AppAPIView):
    """
    Returns pending outgoing call tasks queued from the laptop CRM.
    Mobile app polls this and opens the dialer on the phone.
    """
    parser_classes = [JSONParser]

    def get(self, request):
        from .models import RemoteOutgoingCall
        from django.utils import timezone
        device = services.device_for_user(request.user, **_app_meta(request))
        pending = RemoteOutgoingCall.objects.filter(device=device, is_dispatched=False).order_by('created_at').first()
        if not pending:
            return Response({"has_call": False})

        # Mark dispatched so it doesn't prompt repeatedly
        pending.is_dispatched = True
        pending.dispatched_at = timezone.now()
        pending.save(update_fields=['is_dispatched', 'dispatched_at'])

        raw_number = (pending.phone_number or '').strip()
        clean_number = ''.join(c for c in raw_number if c.isdigit() or c == '+')
        if len(clean_number) == 10 and not clean_number.startswith('+'):
            clean_number = f"+91{clean_number}"

        return Response({
            "has_call": True,
            "call_id": pending.id,
            "call_history_id": pending.call_history_id,
            "phone_number": clean_number or raw_number,
            "lead_id": pending.lead_id,
            "lead_name": pending.lead.name,
            "status": pending.status,
        })


class CallStateReportView(AppAPIView):
    """
    POST /api/calls/report-state/
    Android app reports real-time call states:
      {
        "call_id": 123,
        "state": "DIALING" | "RINGING" | "IN_PROGRESS" | "COMPLETED" | "NO_ANSWER" | "BUSY" | "FAILED",
        "timestamp": "2026-10-11T20:15:00Z",
        "duration_seconds": 45
      }
    """
    parser_classes = [JSONParser]

    def post(self, request):
        from .models import CallStatus, CallOutcome, RemoteOutgoingCall, CallHistory
        from django.db.models import Q
        from django.utils import timezone
        from django.utils.dateparse import parse_datetime

        device = services.device_for_user(request.user, **_app_meta(request))
        data = request.data if isinstance(request.data, dict) else {}

        call_id = data.get("call_id")
        raw_state = str(data.get("state", "")).strip().upper()
        duration_sec = int(data.get("duration_seconds", 0) or 0)
        ts_str = data.get("timestamp")
        event_time = parse_datetime(ts_str) if ts_str else timezone.now()
        if not event_time:
            event_time = timezone.now()

        state_map = {
            "QUEUED": CallStatus.QUEUED,
            "DIALING": CallStatus.DIALING,
            "RINGING": CallStatus.RINGING,
            "IN_PROGRESS": CallStatus.IN_PROGRESS,
            "COMPLETED": CallStatus.COMPLETED,
            "NO_ANSWER": CallStatus.NO_ANSWER,
            "BUSY": CallStatus.BUSY,
            "FAILED": CallStatus.FAILED,
            "CANCELLED": CallStatus.CANCELLED,
        }
        target_status = state_map.get(raw_state)
        if not target_status:
            return Response({"error": f"Invalid state: {raw_state}"}, status=status.HTTP_400_BAD_REQUEST)

        # Lookup by RemoteOutgoingCall id or linked CallHistory id
        remote_call = RemoteOutgoingCall.objects.filter(device=device).filter(
            Q(pk=call_id) | Q(call_history_id=call_id)
        ).first()

        if not remote_call:
            return Response({"error": "Call not found"}, status=status.HTTP_404_NOT_FOUND)

        call_history = remote_call.call_history

        # Terminal states cannot be reverted to earlier states
        terminal_states = (
            CallStatus.COMPLETED, CallStatus.NO_ANSWER, CallStatus.BUSY,
            CallStatus.FAILED, CallStatus.CANCELLED
        )
        if remote_call.status in terminal_states and target_status not in terminal_states:
            return Response({
                "ignored": True,
                "current_status": remote_call.status,
                "message": "Call already finalized"
            })

        # Apply state updates
        remote_call.status = target_status
        if target_status == CallStatus.DIALING and not remote_call.dialed_at:
            remote_call.dialed_at = event_time
        elif target_status == CallStatus.IN_PROGRESS and not remote_call.answered_at:
            remote_call.answered_at = event_time
        elif target_status in terminal_states:
            remote_call.ended_at = event_time
            if duration_sec > 0:
                remote_call.duration = duration_sec
            elif remote_call.answered_at:
                remote_call.duration = max(0, int((event_time - remote_call.answered_at).total_seconds()))

        remote_call.save()

        if call_history:
            if call_history.call_status not in terminal_states or target_status in terminal_states:
                call_history.call_status = target_status
                if target_status == CallStatus.DIALING and not call_history.dialed_at:
                    call_history.dialed_at = event_time
                elif target_status == CallStatus.IN_PROGRESS and not call_history.answered_at:
                    call_history.answered_at = event_time
                elif target_status in terminal_states:
                    call_history.call_ended_at = event_time
                    if duration_sec > 0:
                        call_history.duration = duration_sec
                    elif call_history.answered_at:
                        call_history.duration = max(0, int((event_time - call_history.answered_at).total_seconds()))

                    if target_status == CallStatus.NO_ANSWER:
                        call_history.call_outcome = CallOutcome.NO_ANSWER
                    elif target_status == CallStatus.BUSY:
                        call_history.call_outcome = CallOutcome.BUSY

                call_history.save()

        return Response({
            "success": True,
            "call_id": remote_call.id,
            "call_history_id": call_history.id if call_history else None,
            "status": remote_call.status,
            "duration": remote_call.duration,
        })

