from django.contrib import admin
from .models import BusinessAccount, Conversation, Message


@admin.register(BusinessAccount)
class BusinessAccountAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'phone_number', 'phone_number_id', 'business_account_id', 'is_default', 'is_active', 'created_at')
    list_display_links = ('id', 'name')
    list_filter = ('is_default', 'is_active')
    search_fields = ('name', 'phone_number', 'phone_number_id', 'business_account_id')

    def has_delete_permission(self, request, obj=None):
        """Prevent deleting business accounts from Django admin to avoid accidental admin deletions."""
        return False


class MessageInline(admin.TabularInline):
    model = Message
    extra = 0
    fields = ('sender', 'message_type', 'message_text', 'status', 'timestamp', 'whatsapp_message_id')
    readonly_fields = ('timestamp', 'whatsapp_message_id', 'created_at')
    can_delete = True


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'customer_name',
        'phone_number',
        'business_account',
        'last_message_preview',
        'last_message_time',
        'unread_count',
        'is_pinned',
        'is_online',
        'updated_at'
    )
    list_display_links = ('id', 'customer_name')
    list_filter = ('business_account', 'is_pinned', 'is_archived', 'is_online', 'created_at')
    search_fields = ('customer_name', 'phone_number', 'last_message')
    readonly_fields = ('created_at', 'updated_at')
    inlines = [MessageInline]

    def last_message_preview(self, obj):
        if not obj.last_message:
            return '-'
        return (obj.last_message[:45] + '...') if len(obj.last_message) > 45 else obj.last_message
    last_message_preview.short_description = 'Last Message'


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'conversation_customer',
        'sender',
        'message_type',
        'message_preview',
        'status',
        'whatsapp_message_id',
        'timestamp'
    )
    list_display_links = ('id', 'conversation_customer')
    list_filter = ('sender', 'message_type', 'status', 'timestamp')
    search_fields = (
        'message_text',
        'whatsapp_message_id',
        'conversation__customer_name',
        'conversation__phone_number'
    )
    readonly_fields = ('created_at',)
    date_hierarchy = 'timestamp'

    def conversation_customer(self, obj):
        return f"{obj.conversation.customer_name} ({obj.conversation.phone_number})"
    conversation_customer.short_description = 'Conversation'

    def message_preview(self, obj):
        if obj.message_text:
            return (obj.message_text[:40] + '...') if len(obj.message_text) > 40 else obj.message_text
        if obj.media_file:
            return f"[{obj.message_type.upper()}: {obj.media_file.name}]"
        return '-'
    message_preview.short_description = 'Message Content'
