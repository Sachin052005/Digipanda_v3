"""
CRM Call Sync (Android app) -> CRM leads, follow-ups and call recordings.

    device_for_user()           the app's login user -> CallDevice (auto-created)
    ingest_calls()              Google Ads number calls from the phone's call log
    save_recording()            an uploaded call recording (replaces the Google Drive folder sync)
    mark_called_back()          clear "needs callback" for a lead (+ complete its follow-up)
    leads_with_pending_callback()   role-scoped "missed calls to call back" list

Rules (carried over from TeleCRM_Integrated, mapped onto CRM models):
- One lead per phone number: matched on the last 10 digits of phone OR alternate_phone.
- First source wins: an existing lead keeps its source, status, branch and telecaller.
- Never steal a lead: only an UNASSIGNED lead gets assigned.
- A Google call that creates a lead assigns it to the telecaller whose phone took the call
  (fallback: the branch percentage engine, leads.assignment.assign_new_lead).
- Missed / rejected / 0-second Google call -> needs callback + a Pending FollowUp due in
  CALLBACK_WITHIN_MINUTES (not for closed leads; an earlier pending follow-up wins).
- Recordings never create leads (personal calls stay out of the CRM).
- An answered outgoing recording, or a completed CRM call, clears a pending callback.
"""
import logging
import mimetypes
import os
from datetime import datetime, timedelta, timezone as dt_timezone

from django.db import IntegrityError, transaction
from django.db.models import Count, F, Q
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.utils.module_loading import import_string

from accounts.models import User, UserRole
from activities.utils import log_activity
from followups.models import FollowUp, FollowUpStatus
from leads.duplicates import normalize_phone
from leads.models import Lead, LeadAssignmentHistory, LeadOwnerType, LeadStatus, TelecallerLeadSetup

from . import conf
from .models import CallDevice, CallEvent, CallEventType, CallHistory

log = logging.getLogger('crm')

APP = "Call Sync"

# Leads in these statuses don't get missed-call follow-ups.
CLOSED_STATUSES = (
    LeadStatus.CONVERTED, LeadStatus.JOINED, LeadStatus.LOST,
    LeadStatus.NOT_INTERESTED, LeadStatus.NOT_JOINED, LeadStatus.HISTORICAL,
)


# ------------------------------------------------------------------ helpers

def fmt_duration(seconds):
    seconds = int(seconds or 0)
    if seconds < 60:
        return f"{seconds}s"
    return f"{seconds // 60}m {seconds % 60:02d}s"


def mmss(seconds):
    minutes, secs = divmod(int(seconds or 0), 60)
    hours, minutes = divmod(minutes, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}" if hours else f"{minutes:02d}:{secs:02d}"


def display_name(user):
    if user is None:
        return APP
    return user.get_full_name() or user.username


def phone10(raw):
    """CRM phone format: 10 digits (country code / leading 0 stripped). '' if not a usable number."""
    digits = normalize_phone(raw)
    if not digits or not digits.isdigit() or len(digits) < 10:
        return ''
    return digits[-10:] if len(digits) > 10 and digits.startswith('91') else digits


def find_lead_by_phone(number):
    """Same matching as the Drive recordings: phone or alternate phone, any stored format."""
    from drive.services import find_lead_by_phone as _find
    number = phone10(number)
    if not number:
        return None
    lead = _find(number)
    if lead is not None:
        return lead
    # Numbers saved with spaces/dashes ("+91 98400 12345"): compare normalized digits.
    tail = number[-4:]
    for cand in Lead.objects.filter(Q(phone__endswith=tail) | Q(alternate_phone__endswith=tail)).order_by('pk'):
        if phone10(cand.phone) == number or phone10(cand.alternate_phone) == number:
            return cand
    return None


def add_lead_note(lead, text, user=None):
    """CRM timeline: prepend a dated line to lead.notes (same format as call notes)."""
    stamp = timezone.localtime().strftime('%Y-%m-%d %H:%M')
    current = Lead.objects.filter(pk=lead.pk).values_list('notes', flat=True).first() or ''
    lead.notes = f"[{stamp}] {text}\n" + current
    Lead.objects.filter(pk=lead.pk).update(notes=lead.notes, updated_at=timezone.now())


def device_for_user(user, app_version="", google_sim=None):
    device, _ = CallDevice.objects.get_or_create(user=user)
    fields = ["last_seen_at"]
    device.last_seen_at = timezone.now()
    if app_version and device.app_version != app_version[:20]:
        device.app_version = app_version[:20]
        fields.append("app_version")
    if google_sim is not None and device.google_sim != google_sim[:100]:
        device.google_sim = google_sim[:100]
        fields.append("google_sim")
    device.save(update_fields=fields)
    return device


def can_use_app(user):
    if not user or not user.is_active:
        return False
    if user.is_superuser or user.role in (UserRole.ADMIN, UserRole.SALES_HEAD):
        return True
    return user.role in conf.get("APP_LOGIN_ROLES")


# ------------------------------------------------------------------ assignment

def assign_to_receiver(lead, receiver):
    """
    Give an UNASSIGNED lead to the telecaller whose phone took the Google call.
    Falls back to the branch percentage engine when the receiver isn't an active telecaller.
    Returns True if the lead ended up assigned.
    """
    if lead.assigned_telecaller_id:
        return False

    if receiver is not None and receiver.is_active and receiver.is_telecaller_user:
        from leads.intake import direct_assign
        if lead.branch_id is None:
            lead.branch = receiver.branch
        return direct_assign(lead, receiver,
                             reason=f"{conf.get('GOOGLE_CALL_SOURCE')} received on this telecaller's phone")

    from leads.assignment import assign_new_lead
    branch = lead.branch or getattr(receiver, 'branch', None)
    return assign_new_lead(lead, branch=branch, source=conf.get('GOOGLE_CALL_SOURCE'), triggered_by=receiver)


# ------------------------------------------------------------------ Google-number calls

def _parse_call(item):
    """Validate one call from the phone. Returns a dict or raises ValueError."""
    if not isinstance(item, dict):
        raise ValueError("each call must be an object")
    raw = str(item.get("number") or "").strip()
    phone = phone10(raw)
    if not phone:
        raise ValueError(f"bad number: {raw!r}")
    call_type = item.get("call_type")
    if call_type not in CallEventType.values:
        raise ValueError(f"bad call_type: {call_type!r}")
    ts = int(item["timestamp_ms"])
    return {
        "raw_number": raw[:40],
        "phone": phone,
        "call_type": call_type,
        "started_at": datetime.fromtimestamp(ts / 1000, tz=dt_timezone.utc),
        "duration_sec": max(0, int(item.get("duration_sec") or 0)),
        "sim_account_id": str(item.get("sim_account_id") or "")[:100],
        "contact_name": str(item.get("contact_name") or "").strip()[:150],
    }


def _call_note(event, author):
    when = timezone.localtime(event.started_at).strftime("%d %b, %I:%M %p")
    if event.is_answered:
        return f"📞 Google call answered by {author} ({fmt_duration(event.duration_sec)}) at {when}"
    label = "Rejected" if event.call_type == CallEventType.REJECTED else "Missed"
    return f"📵 {label} Google call at {when} — call back"


def _followup_due(fu):
    """Aware datetime a FollowUp is due (time missing = start of that day)."""
    t = fu.follow_up_time or datetime.min.time()
    return timezone.make_aware(datetime.combine(fu.follow_up_date, t))


def _schedule_callback(lead, event):
    """
    Missed call: make sure a Pending FollowUp is due within CALLBACK_WITHIN_MINUTES.
    Closed leads get none. An existing pending follow-up that is due sooner is reused.
    """
    if lead.status in CLOSED_STATUSES:
        return None
    due = event.started_at + timedelta(minutes=conf.get("CALLBACK_WITHIN_MINUTES"))
    pending = list(FollowUp.objects.filter(lead=lead, status=FollowUpStatus.PENDING))
    sooner = [fu for fu in pending if _followup_due(fu) <= due]
    if sooner:
        followup = min(sooner, key=_followup_due)
    else:
        local_due = timezone.localtime(due)
        owner = lead.assigned_telecaller or event.telecaller
        followup = FollowUp.objects.create(
            lead=lead,
            assigned_user=owner,
            manager=lead.assigned_sales_head,
            telecaller=owner if (owner and owner.is_telecaller_user) else lead.assigned_telecaller,
            follow_up_date=local_due.date(),
            follow_up_time=local_due.time().replace(second=0, microsecond=0),
            status=FollowUpStatus.PENDING,
            notes=f"Missed Google call at {timezone.localtime(event.started_at):%d %b %Y, %I:%M %p} — call back",
        )
    event.followup = followup
    event.save(update_fields=['followup'])
    return followup


def _notify_missed(lead, event):
    recipient = lead.assigned_telecaller or event.telecaller
    if recipient is None:
        return
    try:
        from activities.services import create_notification
        create_notification(
            recipient=recipient,
            title="Missed Google call — call back",
            message=f"{lead.name} ({lead.phone}) called the Google Ads number at "
                    f"{timezone.localtime(event.started_at):%I:%M %p}. Please call back.",
            notification_type="missed_call",
        )
    except Exception:  # notifications must never fail the sync
        log.exception("Missed-call notification failed for lead %s", lead.pk)


def _google_ads_channel():
    from leads.intake import get_channel
    return get_channel("Google Ads")


def ingest_calls(device, calls):
    """Google Ads number calls from the phone's call log. Returns a summary dict for the app."""
    result = {"created": 0, "duplicates": 0, "new_leads": 0, "errors": []}
    on_missed = conf.get("ON_MISSED_CALL")
    on_missed = import_string(on_missed) if on_missed else None
    receiver = device.user
    author = display_name(receiver)
    source = conf.get("GOOGLE_CALL_SOURCE")

    for i, item in enumerate(calls):
        try:
            data = _parse_call(item)
        except (KeyError, TypeError, ValueError) as e:
            result["errors"].append({"index": i, "error": str(e)})
            continue

        if CallEvent.objects.filter(device=device, raw_number=data["raw_number"],
                                    started_at=data["started_at"]).exists():
            result["duplicates"] += 1
            continue

        try:
            with transaction.atomic():
                event = CallEvent(device=device, telecaller=receiver, **data)
                event.needs_callback = not event.is_answered

                from leads.intake import intake_lead
                call_event_id = f"gcall_{device.id}_{data['raw_number']}_{data['started_at'].isoformat() if hasattr(data['started_at'], 'isoformat') else data['started_at']}"
                note_text = _call_note(event, author)

                intake_res = intake_lead(
                    phone=data["phone"],
                    source=source,
                    channel_name="Google Ads",
                    name=(data["contact_name"] or data["phone"])[:150],
                    branch=receiver.branch,
                    note=note_text,
                    activity_user=receiver,
                    provider_event_id=call_event_id,
                    incoming_timestamp=data["started_at"],
                    data_payload={"raw_number": data.get("raw_number"), "started_at": str(data.get("started_at"))}
                )
                lead = intake_res.lead
                created_lead = intake_res.created

                event.lead = lead
                event.is_new_lead = created_lead
                event.save()

                if not lead.assigned_telecaller_id:
                    assign_to_receiver(lead, receiver)
                    lead.refresh_from_db()
                if event.needs_callback:
                    _schedule_callback(lead, event)
                log_activity(user=receiver, action="Google Call Synced", description=f"{lead.name}: {note_text}",
                             object_type="Lead", object_id=lead.pk)

        except IntegrityError:
            result["duplicates"] += 1  # same call arrived twice at the same moment
            continue

        result["created"] += 1
        result["new_leads"] += int(created_lead)

        if event.needs_callback:
            _notify_missed(lead, event)
            if on_missed:
                try:
                    on_missed(event)
                except Exception:  # never fail the sync because of a hook
                    log.exception("ON_MISSED_CALL hook failed for call %s", event.pk)

    device.last_call_sync_at = timezone.now()
    device.save(update_fields=["last_call_sync_at"])
    return result


def mark_called_back(lead, by=None):
    """Clear pending missed-call callbacks for a lead and complete their follow-ups. Returns count."""
    events = list(lead.call_events.filter(needs_callback=True))
    if not events:
        return 0
    by_name = display_name(by) if not isinstance(by, str) else by
    followup_ids = [e.followup_id for e in events if e.followup_id]
    CallEvent.objects.filter(pk__in=[e.pk for e in events]).update(
        needs_callback=False, called_back_at=timezone.now(), called_back_by=str(by_name)[:150])
    if followup_ids:
        FollowUp.objects.filter(pk__in=followup_ids, status=FollowUpStatus.PENDING).update(
            status=FollowUpStatus.COMPLETED, updated_at=timezone.now())
    return len(events)


def leads_with_pending_callback(user):
    """Role-scoped leads that have a missed Google call waiting for a call back."""
    from accounts.permissions import get_accessible_branch_ids
    qs = Lead.objects.filter(call_events__needs_callback=True).distinct()
    if not user.is_authenticated:
        return qs.none()
    if user.is_admin_user:
        return qs
    if user.role == UserRole.SALES_HEAD:
        return qs.filter(branch_id__in=get_accessible_branch_ids(user))
    if user.role in (UserRole.BRANCH_HEAD, UserRole.COUNSELOR):
        return qs.filter(branch_id=user.branch_id)
    if user.is_telecaller_user:
        return qs.filter(assigned_telecaller=user)
    return qs.none()


# ------------------------------------------------------------------ recordings

class RecordingRejected(ValueError):
    """Bad file: the app skips it instead of retrying forever (HTTP 400)."""


def match_call_for_recording(phone, recorded_at, tolerance_sec=None):
    """The Google call a recording belongs to (same number, close in time)."""
    if not phone or recorded_at is None:
        return None
    tolerance = timedelta(seconds=tolerance_sec or conf.get("MATCH_WINDOW_SECONDS"))
    candidates = CallEvent.objects.filter(
        phone__endswith=phone[-10:],
        started_at__gte=recorded_at - tolerance,
        started_at__lte=recorded_at + tolerance,
    )
    return min(candidates, key=lambda e: abs(e.started_at - recorded_at), default=None)


def match_call_history(lead, user, recorded_at, tolerance_sec=None):
    """The CRM call (Call button -> notes) this recording belongs to: same lead, closest start time."""
    if lead is None:
        return None
    qs = CallHistory.objects.filter(lead=lead)
    if recorded_at is None:
        mine = qs.filter(Q(caller=user) | Q(telecaller=user)).order_by('-call_started_at').first()
        return mine
    tolerance = timedelta(seconds=tolerance_sec or conf.get("MATCH_WINDOW_SECONDS"))
    candidates = list(qs.filter(call_started_at__gte=recorded_at - tolerance,
                                call_started_at__lte=recorded_at + tolerance))
    if not candidates:
        return None
    # Prefer this telecaller's own call, then the closest in time.
    return min(candidates, key=lambda c: (c.caller_id != user.pk and c.telecaller_id != user.pk,
                                          abs(c.call_started_at - recorded_at)))


def _parse_started_at(value):
    if not value:
        return None
    dt = parse_datetime(str(value).strip())
    if dt is None:
        return None
    return dt if timezone.is_aware(dt) else timezone.make_aware(dt, dt_timezone.utc)


def save_recording(device, upload, data):
    """
    data = the app's form fields: device_file_id, phone_number, direction,
    duration_seconds, call_started_at. Returns (drive.CallRecording, created).
    """
    from drive.models import CallRecording

    if upload is None:
        raise RecordingRejected("audio_file is required")
    ext = os.path.splitext(upload.name)[1].lower().lstrip(".")
    if ext not in conf.get("ALLOWED_AUDIO_EXTENSIONS"):
        raise RecordingRejected(f"unsupported file type: .{ext or '?'}")
    max_mb = conf.get("MAX_RECORDING_MB")
    if upload.size > max_mb * 1024 * 1024:
        raise RecordingRejected(f"file larger than {max_mb} MB")

    device_file_id = str(data.get("device_file_id") or "").strip()[:64]
    if not device_file_id:
        raise RecordingRejected("device_file_id is required")
    existing = CallRecording.objects.filter(device=device, device_file_id=device_file_id).first()
    if existing:
        return existing, False

    raw_number = str(data.get("phone_number") or "").strip()[:30]
    phone = phone10(raw_number)
    direction = str(data.get("direction") or "unknown").lower()
    if direction not in dict(CallRecording.DIRECTION_CHOICES):
        direction = "unknown"
    try:
        duration = max(0, int(float(data.get("duration_seconds") or 0)))
    except (TypeError, ValueError):
        duration = 0
    started_at = _parse_started_at(data.get("call_started_at"))
    user = device.user

    # Recordings never create leads: personal calls stay out of the CRM.
    lead = find_lead_by_phone(phone) if phone else None
    event = match_call_for_recording(phone, started_at) if phone else None
    if lead is None and event is not None:
        lead = event.lead
    call_history = match_call_history(lead, user, started_at)

    if lead is not None:
        match_status, reason = 'MATCHED', ''
    elif phone:
        match_status, reason = 'UNMATCHED', f'No matching CRM lead found (phone: {phone})'
    else:
        match_status, reason = 'UNMATCHED', 'Mobile number could not be identified'

    file_name = os.path.basename(upload.name)[:255]
    mime = (getattr(upload, 'content_type', '') or '').lower()
    if not mime.startswith('audio/') and not mime.startswith('video/'):
        mime = mimetypes.guess_type(file_name)[0] or 'audio/mpeg'

    try:
        with transaction.atomic():
            rec = CallRecording(
                source=CallRecording.SOURCE_APP,
                device=device,
                device_file_id=device_file_id,
                telecaller=user,
                lead=lead,
                call_history=call_history,
                call_event=event,
                drive_file_id=None,
                file_name=file_name,
                mobile_number=raw_number,
                normalized_mobile_number=phone,
                mime_type=mime[:50],
                duration=mmss(duration),
                duration_seconds=duration,
                file_size=upload.size,
                direction=direction,
                archive_status='ARCHIVED',
                match_status=match_status,
                unmatched_reason=reason,
                recording_date=started_at or timezone.now(),
            )
            rec.audio_file.save(file_name, upload, save=False)
            rec.save()
    except IntegrityError:  # same file uploaded twice at the same moment
        if rec.audio_file:
            rec.audio_file.delete(save=False)
        return CallRecording.objects.get(device=device, device_file_id=device_file_id), False

    device.last_recording_at = timezone.now()
    device.save(update_fields=["last_recording_at"])

    # The phone's real call length is better than the browser timer when the CRM call shows 0.
    if call_history is not None and duration > 0 and not call_history.duration:
        CallHistory.objects.filter(pk=call_history.pk).update(duration=duration, updated_at=timezone.now())

    if lead is not None:
        author = display_name(user)
        label = f"{direction.title()} call recording" if direction != 'unknown' else "Call recording"
        add_lead_note(lead, f"🎙️ {label} by {author} ({fmt_duration(duration)})")
        log_activity(user=user, action="Call Recording Synced",
                     description=f"{label} ({fmt_duration(duration)}) for lead '{lead.name}' uploaded from {APP}.",
                     object_type="CallRecording", object_id=rec.pk)
        # An answered outgoing call to this number clears any pending missed-call callback.
        if direction == "outgoing" and duration > 0:
            if mark_called_back(lead, by=user):
                add_lead_note(lead, f"✅ Missed Google call returned by {author}")
    return rec, True
