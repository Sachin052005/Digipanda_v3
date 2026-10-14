from django.contrib import admin
from .models import CallRecording


@admin.register(CallRecording)
class CallRecordingAdmin(admin.ModelAdmin):
    list_display = (
        'file_name', 'source', 'mobile_number', 'normalized_mobile_number',
        'direction', 'duration', 'match_status', 'lead', 'telecaller', 'recording_date'
    )
    search_fields = ('file_name', 'mobile_number', 'normalized_mobile_number', 'device_file_id')
    list_filter = ('source', 'match_status', 'direction', 'telecaller', 'created_at')
    raw_id_fields = ('lead', 'call_history', 'call_event', 'device', 'telecaller')
    exclude = ('audio_data', 'drive_connection', 'drive_file_id', 'drive_url', 'source_folder_id', 'archive_status')
