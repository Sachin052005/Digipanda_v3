from rest_framework import serializers
from .models import BusinessAccount, Conversation, Message, AutomationFlow, UserFlowSession, Course, Branch


class AutomationFlowSerializer(serializers.ModelSerializer):
    active_sessions_count = serializers.SerializerMethodField()
    completed_sessions_count = serializers.SerializerMethodField()
    trigger_keywords = serializers.CharField(required=False, allow_blank=True, default='')
    slug = serializers.CharField(required=False, allow_blank=True, default='')

    class Meta:
        model = AutomationFlow
        fields = [
            'id',
            'business_account',
            'name',
            'slug',
            'version',
            'status',
            'trigger_type',
            'trigger_keywords',
            'flow_data',
            'is_active',
            'published_at',
            'active_sessions_count',
            'completed_sessions_count',
            'created_at',
            'updated_at'
        ]

    def get_active_sessions_count(self, obj):
        if hasattr(obj, 'sessions'):
            return obj.sessions.filter(status=UserFlowSession.STATUS_ACTIVE).count()
        return 0

    def get_completed_sessions_count(self, obj):
        if hasattr(obj, 'sessions'):
            return obj.sessions.filter(status=UserFlowSession.STATUS_COMPLETED).count()
        return 0


class UserFlowSessionSerializer(serializers.ModelSerializer):
    flow_name = serializers.CharField(source='flow.name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = UserFlowSession
        fields = [
            'id',
            'conversation',
            'flow',
            'flow_name',
            'flow_version',
            'current_node_id',
            'waiting_for_input',
            'status',
            'status_display',
            'collected_data',
            'started_at',
            'updated_at',
            'paused_at',
            'handed_over_at',
            'completed_at',
            'expires_at',
        ]


class BusinessAccountSerializer(serializers.ModelSerializer):
    unread_count = serializers.SerializerMethodField()
    active_flow_info = serializers.SerializerMethodField()
    crm_branch_id = serializers.IntegerField(source='crm_branch.id', read_only=True)
    crm_branch_name = serializers.CharField(source='crm_branch.name', read_only=True)

    class Meta:
        model = BusinessAccount
        fields = [
            'id',
            'name',
            'phone_number',
            'phone_number_id',
            'business_account_id',
            'is_default',
            'is_active',
            'automation_enabled',
            'crm_branch',
            'crm_branch_id',
            'crm_branch_name',
            'unread_count',
            'active_flow_info',
        ]
        extra_kwargs = {
            'crm_branch': {'required': False, 'allow_null': True}
        }

    def get_unread_count(self, obj):
        return sum(conv.unread_count for conv in obj.conversations.filter(is_archived=False))

    def get_active_flow_info(self, obj):
        flow = obj.automation_flows.filter(is_active=True, status=AutomationFlow.STATUS_PUBLISHED).first()
        if not flow:
            flow = AutomationFlow.objects.filter(business_account__isnull=True, is_active=True, status=AutomationFlow.STATUS_PUBLISHED).first()
        if flow:
            return {
                'id': flow.id,
                'name': flow.name,
                'version': flow.version,
                'status': flow.status
            }
        return None


class ConversationSerializer(serializers.ModelSerializer):
    last_message_time_display = serializers.CharField(source='display_time', read_only=True)
    profile_image_url = serializers.SerializerMethodField()
    business_account_id = serializers.IntegerField(source='business_account.id', read_only=True)
    business_account_name = serializers.CharField(source='business_account.name', read_only=True)

    automation_status = serializers.SerializerMethodField()

    class Meta:
        model = Conversation
        fields = [
            'id',
            'business_account_id',
            'business_account_name',
            'customer_name',
            'phone_number',
            'profile_image',
            'profile_image_url',
            'last_message',
            'last_message_time',
            'last_message_time_display',
            'unread_count',
            'is_pinned',
            'is_archived',
            'is_online',
            'last_seen',
            'automation_status',
            'created_at',
            'updated_at',
        ]

    def get_automation_status(self, obj):
        session = obj.flow_sessions.order_by('-updated_at').first()
        return session.status if session else None

    def get_profile_image_url(self, obj):
        if obj.profile_image:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.profile_image.url)
            return obj.profile_image.url
        return None

    def to_representation(self, instance):
        data = super().to_representation(instance)
        # Ensure 'last_message_time' is formatted for display when consumed by UI
        data['last_message_time'] = instance.display_time
        return data


class MessageSerializer(serializers.ModelSerializer):
    conversation_id = serializers.IntegerField(source='conversation.id', read_only=True)
    display_time = serializers.CharField(read_only=True)
    media_url = serializers.SerializerMethodField()
    media_filename = serializers.SerializerMethodField()

    class Meta:
        model = Message
        fields = [
            'id',
            'conversation_id',
            'sender',
            'message_type',
            'message_text',
            'media_file',
            'media_url',
            'media_filename',
            'whatsapp_message_id',
            'status',
            'timestamp',
            'display_time',
            'created_at',
        ]

    def get_media_url(self, obj):
        if obj.media_file:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.media_file.url)
            return obj.media_file.url
        return None

    def get_media_filename(self, obj):
        if obj.media_file:
            import os
            return os.path.basename(obj.media_file.name)
        return None


class SendMessageInputSerializer(serializers.Serializer):
    conversation_id = serializers.IntegerField(required=False, allow_null=True)
    business_account_id = serializers.IntegerField(required=False, allow_null=True)
    customer_name = serializers.CharField(required=False, allow_blank=True, default='')
    phone_number = serializers.CharField(required=False, allow_blank=True, default='')
    message_text = serializers.CharField(required=False, allow_blank=True, default='')
    message_type = serializers.ChoiceField(
        choices=Message.MESSAGE_TYPE_CHOICES,
        default=Message.TYPE_TEXT
    )
    media_file = serializers.FileField(required=False, allow_null=True)

    def validate(self, attrs):
        conv_id = attrs.get('conversation_id')
        phone = attrs.get('phone_number')
        if not conv_id and not phone:
            raise serializers.ValidationError("Either conversation_id or phone_number must be provided.")
        text = attrs.get('message_text', '').strip()
        media = attrs.get('media_file')
        if not text and not media:
            raise serializers.ValidationError("Either message_text or media_file must be provided.")
        return attrs
