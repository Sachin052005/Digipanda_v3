"""
Call recordings (from the CRM Call Sync Android app).

The Google Drive folder sync has been removed: recordings now come only from telecaller phones
(calls/api_views.py -> calls/sync_services.save_recording). The app keeps its old name ("drive")
and table so existing recordings stay playable.

    call_recordings_list    role-scoped list with search / filters / player
    recordings_retry_match  re-match unmatched recordings against current leads (Admin / Sales Head)
    drive_stream_recording  streams one recording after role checks (audio player source)
"""
import logging
from datetime import datetime, time

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import FileResponse, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.models import User
from accounts.permissions import get_accessible_branch_ids
from activities.utils import log_activity

from .models import CallRecording
from .services import get_user_recordings_queryset, retry_matching_unmatched_recordings

logger = logging.getLogger('crm')


def _parse_date(value):
    try:
        return datetime.strptime(value, '%Y-%m-%d').date() if value else None
    except ValueError:
        return None


@login_required
def call_recordings_list(request):
    """All call recordings this user may listen to, newest call first."""
    user = request.user
    qs = get_user_recordings_queryset(user).select_related('lead', 'telecaller', 'lead__branch')
    can_see_unmatched = user.is_admin_user or user.is_sales_head_user

    f = {
        'q': request.GET.get('q', '').strip(),
        'telecaller': request.GET.get('telecaller', '').strip(),
        'match': request.GET.get('match', '').strip(),
        'direction': request.GET.get('direction', '').strip(),
        'date_from': request.GET.get('date_from', '').strip(),
        'date_to': request.GET.get('date_to', '').strip(),
    }
    if f['q']:
        qs = qs.filter(Q(lead__name__icontains=f['q']) | Q(normalized_mobile_number__icontains=f['q'])
                       | Q(mobile_number__icontains=f['q']) | Q(file_name__icontains=f['q']))
    if f['telecaller'].isdigit():
        qs = qs.filter(telecaller_id=int(f['telecaller']))
    if f['match'] in ('MATCHED', 'UNMATCHED'):
        qs = qs.filter(match_status=f['match'])
    if f['direction'] in ('incoming', 'outgoing', 'unknown'):
        qs = qs.filter(direction=f['direction'])
    d_from, d_to = _parse_date(f['date_from']), _parse_date(f['date_to'])
    if d_from:
        dt_from = timezone.make_aware(datetime.combine(d_from, time.min))
        qs = qs.filter(recording_date__gte=dt_from)
    if d_to:
        dt_to = timezone.make_aware(datetime.combine(d_to, time.max))
        qs = qs.filter(recording_date__lte=dt_to)

    total = qs.count()
    unmatched = qs.filter(match_status='UNMATCHED').count() if can_see_unmatched else 0
    page_obj = Paginator(qs.order_by('-recording_date', '-created_at'), 25).get_page(request.GET.get('page'))
    query = request.GET.copy()
    query.pop('page', None)

    if user.is_admin_user:
        telecallers = User.get_telecallers_queryset()
    elif user.is_telecaller_user:
        telecallers = User.objects.filter(pk=user.pk)
    else:
        telecallers = User.get_telecallers_queryset().filter(branch_id__in=get_accessible_branch_ids(user))

    if user.is_admin_user:
        lead_url = 'admin_lead_detail'
    elif user.is_sales_head_user:
        lead_url = 'manager_lead_detail'
    elif user.is_branch_head_user:
        lead_url = 'branch_head_lead_detail'
    elif user.is_counselor_user:
        lead_url = 'counselor_lead_detail'
    else:
        lead_url = 'telecaller_lead_detail'

    return render(request, 'calls/recordings_list.html', {
        'page_obj': page_obj,
        'f': f,
        'query_string': query.urlencode(),
        'total': total,
        'unmatched': unmatched,
        'today': qs.filter(recording_date__date=timezone.localdate()).count(),
        'can_see_unmatched': can_see_unmatched,
        'telecallers': telecallers.order_by('first_name', 'username'),
        'lead_url_name': lead_url,
    })


@login_required
@require_POST
def recordings_retry_match(request):
    if not (request.user.is_admin_user or request.user.is_sales_head_user):
        raise PermissionDenied("Only Admin and Sales Head can re-match recordings.")
    n = retry_matching_unmatched_recordings(request.user)
    log_activity(user=request.user, action="Recordings Re-matched",
                 description=f"{n} unmatched call recording(s) matched to leads.", object_type="CallRecording",
                 request=request)
    messages.success(request, f"{n} recording(s) matched to leads." if n else "No new matches found.")
    return redirect('call_recordings_list')


@login_required
def drive_stream_recording(request, recording_id):
    """
    Serves recording audio with strict role-based access validation.
    Call Sync recordings stream from private_media/; old archived rows from the database.
    """
    recording = get_object_or_404(CallRecording, pk=recording_id)

    # Permission: same role rules as the Call Recordings list
    if not get_user_recordings_queryset(request.user).filter(pk=recording.pk).exists():
        raise PermissionDenied("Access denied: You do not have permission to access this recording.")

    # App recordings (CRM Call Sync): stream the file from private_media/ (supports seeking)
    if recording.audio_file:
        return _stream_recording_file(request, recording)

    # Return audio stream from MySQL binary storage
    if not recording.audio_data or len(recording.audio_data) == 0:
        return HttpResponse("Recording audio binary is not available.", status=404)

    audio_content = bytes(recording.audio_data)
    content_type = recording.mime_type or 'audio/mpeg'
    if content_type.startswith('video/mpeg') or content_type == 'application/octet-stream':
        content_type = 'audio/mpeg'
    elif audio_content.startswith(b'\xff\xfb') or audio_content.startswith(b'ID3'):
        content_type = 'audio/mpeg'
    file_size = len(audio_content)

    # HTTP 206 Partial Content support for seeking
    http_range = request.META.get('HTTP_RANGE', '')
    if http_range and http_range.startswith('bytes='):
        ranges = http_range[6:].split('-')
        start = int(ranges[0]) if ranges[0] else 0
        end = int(ranges[1]) if (len(ranges) > 1 and ranges[1]) else file_size - 1
        start = max(0, min(start, file_size - 1))
        end = max(start, min(end, file_size - 1))
        length = end - start + 1

        response = HttpResponse(audio_content[start:end + 1], status=206, content_type=content_type)
        response['Content-Range'] = f'bytes {start}-{end}/{file_size}'
        response['Content-Length'] = str(length)
    else:
        response = HttpResponse(audio_content, content_type=content_type)
        response['Content-Length'] = str(file_size)

    response['Content-Disposition'] = f'inline; filename="{recording.file_name}"'
    response['Accept-Ranges'] = 'bytes'
    response['Cache-Control'] = 'private, max-age=86400'
    return response


def _stream_recording_file(request, recording):
    """Serve an app recording file with HTTP Range support. Permission checks happen before this."""
    import mimetypes
    try:
        fh = recording.audio_file.open('rb')
    except (FileNotFoundError, OSError):
        return HttpResponse("Recording file is missing on the server.", status=404)

    content_type = recording.mime_type or mimetypes.guess_type(recording.file_name)[0] or 'audio/mpeg'
    if content_type == 'application/octet-stream':
        content_type = 'audio/mpeg'
    file_size = recording.audio_file.size

    http_range = request.META.get('HTTP_RANGE', '')
    if http_range.startswith('bytes=') and file_size:
        ranges = http_range[6:].split('-')
        try:
            start = int(ranges[0]) if ranges[0] else 0
            end = int(ranges[1]) if (len(ranges) > 1 and ranges[1]) else file_size - 1
        except ValueError:
            start, end = 0, file_size - 1
        start = max(0, min(start, file_size - 1))
        end = max(start, min(end, file_size - 1))
        fh.seek(start)
        data = fh.read(end - start + 1)
        fh.close()
        response = HttpResponse(data, status=206, content_type=content_type)
        response['Content-Range'] = f'bytes {start}-{end}/{file_size}'
        response['Content-Length'] = str(len(data))
    else:
        response = FileResponse(fh, content_type=content_type)
        response['Content-Length'] = str(file_size)

    response['Content-Disposition'] = f'inline; filename="{recording.file_name}"'
    response['Accept-Ranges'] = 'bytes'
    response['Cache-Control'] = 'private, max-age=86400'
    return response
