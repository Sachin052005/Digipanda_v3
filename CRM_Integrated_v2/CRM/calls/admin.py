from django.contrib import admin
from .models import CallHistory

@admin.register(CallHistory)
class CallHistoryAdmin(admin.ModelAdmin):
    list_display = ('lead', 'caller', 'manager', 'telecaller', 'duration', 'call_status', 'call_outcome', 'call_started_at')
    list_filter = ('call_status', 'call_outcome', 'manager', 'telecaller', 'call_started_at')
    search_fields = ('lead__name', 'lead__phone', 'caller__username', 'notes')
    ordering = ('-call_started_at',)


from .models import CallDevice, CallEvent


@admin.register(CallDevice)
class CallDeviceAdmin(admin.ModelAdmin):
    list_display = ('user', 'google_sim_label', 'app_version', 'last_seen_at', 'last_call_sync_at', 'last_recording_at')
    search_fields = ('user__username', 'user__first_name', 'user__last_name')
    readonly_fields = ('created_at',)

    @admin.display(description='Google Ads number')
    def google_sim_label(self, obj):
        if not obj.google_sim:
            return 'Off'
        return 'All SIMs' if obj.google_sim == 'all' else f'SIM {obj.google_sim}'


@admin.register(CallEvent)
class CallEventAdmin(admin.ModelAdmin):
    list_display = ('phone', 'call_type', 'started_at', 'duration_sec', 'telecaller', 'lead', 'is_new_lead',
                    'needs_callback', 'called_back_at')
    list_filter = ('call_type', 'needs_callback', 'is_new_lead', 'telecaller')
    search_fields = ('phone', 'raw_number', 'contact_name', 'lead__name')
    raw_id_fields = ('lead', 'followup', 'device', 'telecaller')
    ordering = ('-started_at',)
