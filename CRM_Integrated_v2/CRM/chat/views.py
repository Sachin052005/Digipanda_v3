"""
Django views and API endpoints for WhatsApp CRM.
"""

import json
import logging
from django.shortcuts import render, get_object_or_404
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.views import View
from django.db.models import Q
from django.utils import timezone
from django.utils.text import slugify
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import BasePermission

from . import crm

from .models import BusinessAccount, Conversation, Message, AutomationFlow, UserFlowSession
from .serializers import (
    BusinessAccountSerializer,
    ConversationSerializer,
    MessageSerializer,
    SendMessageInputSerializer,
    AutomationFlowSerializer,
    UserFlowSessionSerializer
)
from .whatsapp.client import WhatsAppClient
from .whatsapp.messages import send_text_message, send_media_message
from .whatsapp.webhook import (
    verify_webhook_token,
    process_incoming_message,
    process_message_status
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# CRM access rules
#   Inbox: any logged-in CRM user; each user only sees chats of leads they can see.
#   Automations (flow builder) and WhatsApp numbers: Admin and Sales Head.
# ---------------------------------------------------------------------------

class IsInboxUser(BasePermission):
    def has_permission(self, request, view):
        return crm.can_use_inbox(request.user)


class CanManageAutomation(BasePermission):
    message = "Only Admin and Sales Head can manage WhatsApp automations and numbers."

    def has_permission(self, request, view):
        return crm.can_manage_automation(request.user)


class AutomationPageMixin(LoginRequiredMixin):
    login_url = 'login'

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and not crm.can_manage_automation(request.user):
            raise PermissionDenied("Only Admin and Sales Head can manage WhatsApp automations.")
        return super().dispatch(request, *args, **kwargs)


def _conversation_or_403(user, pk):
    conversation = get_object_or_404(Conversation, pk=pk)
    if not crm.can_open_conversation(user, conversation):
        raise PermissionDenied("You can only open chats of your own leads.")
    return conversation


def broadcast_event(group_name: str, event_data: dict):
    """Utility to safely dispatch channel events."""
    try:
        channel_layer = get_channel_layer()
        if channel_layer:
            async_to_sync(channel_layer.group_send)(group_name, event_data)
    except Exception as exc:
        logger.warning(f"Failed to dispatch channel event to {group_name}: {exc}")


class InboxView(LoginRequiredMixin, View):
    """
    Renders the main WhatsApp CRM single-page inbox.
    Only two panels: CONVERSATIONS (left) and CHAT (right).
    """
    login_url = 'login'

    def get(self, request):
        return render(request, 'chat/inbox.html', {
            'can_manage_automation': crm.can_manage_automation(request.user),
        })


class AutomationListView(AutomationPageMixin, View):
    """
    Renders the modern SaaS Automations List Dashboard.
    """
    def get(self, request):
        return render(request, 'chat/automation_list.html')


class FlowBuilderView(AutomationPageMixin, View):
    """
    Renders the visual No-Code Flow Builder page.
    """
    def get(self, request, pk=None):
        return render(request, 'chat/flow_builder.html')


class BusinessAccountListAPI(APIView):
    """
    GET /api/business-accounts/
    Returns list of configured WhatsApp Business accounts.
    """
    def get(self, request):
        import os
        accounts = BusinessAccount.objects.filter(is_active=True)
        if not accounts.exists():
            phone_id = os.getenv('WHATSAPP_PHONE_NUMBER_ID', '')
            if phone_id:
                BusinessAccount.objects.create(
                    name="Home AI Line",
                    phone_number="+91 84382 39448",
                    phone_number_id=phone_id,
                    is_default=True,
                    is_active=True
                )
                accounts = BusinessAccount.objects.filter(is_active=True)

        serializer = BusinessAccountSerializer(accounts, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request):
        """
        POST /api/business-accounts/
        Create a new WhatsApp Business number/account.
        """
        if not crm.can_manage_automation(request.user):
            raise PermissionDenied("Only Admin and Sales Head can add WhatsApp numbers.")
        serializer = BusinessAccountSerializer(data=request.data)
        if serializer.is_valid():
            account = serializer.save()
            return Response(BusinessAccountSerializer(account).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class BusinessAccountDetailAPI(APIView):
    """
    DELETE /api/business-accounts/<id>/
    Removes or deactivates a business number.
    """
    def patch(self, request, pk):
        """
        PATCH /api/business-accounts/<id>/
        Update settings (e.g. toggle automation_enabled on/off).
        """
        account = get_object_or_404(BusinessAccount, pk=pk)
        if 'automation_enabled' in request.data:
            account.automation_enabled = bool(request.data['automation_enabled'])
            account.save(update_fields=['automation_enabled'])
        serializer = BusinessAccountSerializer(account)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def delete(self, request, pk):
        account = get_object_or_404(BusinessAccount, pk=pk)
        account_name = account.name
        account.delete()
        return Response({'message': f'Business line "{account_name}" removed successfully.'}, status=status.HTTP_200_OK)


class ConversationListAPI(APIView):
    """
    GET /api/conversations/
    Returns conversations, filtered by business_account_id and unread status.
    """
    def get(self, request):
        filter_type = request.query_params.get('filter', 'all')
        business_account_id = request.query_params.get('business_account_id')
        queryset = crm.conversations_for_user(request.user, Conversation.objects.filter(is_archived=False))

        if business_account_id:
            queryset = queryset.filter(business_account_id=business_account_id)

        if filter_type == 'unread':
            queryset = queryset.filter(unread_count__gt=0)

        serializer = ConversationSerializer(queryset, many=True, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)


class ConversationMessagesAPI(APIView):
    """
    GET /api/conversations/<id>/messages/
    Returns chronological messages for a conversation and marks unread count as 0.
    """
    def get(self, request, pk):
        conversation = _conversation_or_403(request.user, pk)

        # Mark as read when the agent opens this conversation
        if conversation.unread_count > 0:
            conversation.mark_as_read()
            # Broadcast unread count reset to inbox
            broadcast_event("inbox_updates", {
                "type": "conversation_update",
                "conversation": {
                    "id": conversation.id,
                    "business_account_id": conversation.business_account_id,
                    "customer_name": conversation.customer_name,
                    "phone_number": conversation.phone_number,
                    "last_message": conversation.last_message,
                    "last_message_time": conversation.display_time,
                    "unread_count": 0,
                }
            })

        messages = conversation.messages.all().order_by('timestamp', 'created_at')
        serializer = MessageSerializer(messages, many=True, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)


class SendMessageAPI(APIView):
    """
    POST /api/messages/send/
    Sends an outbound message to a customer from the CRM inbox.
    Uses the conversation's bound BusinessAccount credentials.
    """
    def post(self, request):
        serializer = SendMessageInputSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({"error": "Invalid data", "details": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

        conversation_id = serializer.validated_data.get('conversation_id')
        business_account_id = serializer.validated_data.get('business_account_id')
        phone_number = serializer.validated_data.get('phone_number', '').strip()
        customer_name = serializer.validated_data.get('customer_name', '').strip()
        message_text = serializer.validated_data.get('message_text', '').strip()
        message_type = serializer.validated_data.get('message_type', Message.TYPE_TEXT)
        media_file = serializer.validated_data.get('media_file')

        if conversation_id:
            conversation = _conversation_or_403(request.user, conversation_id)
        else:
            from .whatsapp.webhook import format_phone_e164
            clean_phone = format_phone_e164(phone_number)
            if not crm.can_manage_automation(request.user):
                # Starting a new chat: only with a lead this user can see.
                from accounts.permissions import can_access_lead
                lead = crm.intake.find_lead_by_phone(clean_phone)
                if lead is None or not can_access_lead(request.user, lead):
                    raise PermissionDenied("You can only message your own leads.")
            business_account = None
            if business_account_id:
                business_account = BusinessAccount.objects.filter(pk=business_account_id).first()
            if not business_account:
                business_account = BusinessAccount.objects.filter(is_default=True).first() or BusinessAccount.objects.first()

            conversation, _ = Conversation.objects.get_or_create(
                business_account=business_account,
                phone_number=clean_phone,
                defaults={
                    'customer_name': customer_name or clean_phone,
                    'is_online': True,
                    'last_seen': 'online',
                }
            )
            if customer_name and conversation.customer_name != customer_name:
                conversation.customer_name = customer_name
                conversation.save(update_fields=['customer_name'])
        now = timezone.now()

        # Create message record
        message = Message.objects.create(
            conversation=conversation,
            sender=Message.SENDER_AGENT,
            message_type=message_type,
            message_text=message_text,
            media_file=media_file,
            status=Message.STATUS_SENT,
            timestamp=now
        )

        # Update preview in conversation
        display_preview = message_text if message_text else f"[{message_type.title()}]"
        conversation.last_message = display_preview
        conversation.last_message_time = now
        conversation.save(update_fields=['last_message', 'last_message_time', 'updated_at'])

        # Attempt WhatsApp Cloud API dispatch with conversation's business_account
        whatsapp_msg_id = ""
        whatsapp_error_text = ""
        try:
            if message_type == Message.TYPE_TEXT:
                wa_res = send_text_message(
                    conversation.phone_number,
                    message_text,
                    business_account=conversation.business_account
                )
                messages_data = wa_res.get('messages', [])
                if messages_data:
                    whatsapp_msg_id = messages_data[0].get('id', '')
            elif media_file:
                client = WhatsAppClient(business_account=conversation.business_account)
                # Upload directly to Meta Media API for 100% reliable delivery
                mime_type = getattr(media_file, 'content_type', 'application/octet-stream')
                try:
                    if hasattr(message.media_file, 'path'):
                        media_id = client.upload_media(message.media_file.path, mime_type=mime_type)
                    else:
                        media_id = client.upload_media(media_file, mime_type=mime_type)
                except Exception as upload_err:
                    logger.warning(f"Direct media upload to Meta failed, falling back to URL: {upload_err}")
                    media_id = request.build_absolute_uri(message.media_file.url)

                original_filename = getattr(media_file, 'name', '')
                if original_filename:
                    import os
                    original_filename = os.path.basename(original_filename)

                wa_res = send_media_message(
                    to_phone_number=conversation.phone_number,
                    media_type=message_type,
                    media_url_or_id=media_id,
                    caption=message_text,
                    filename=original_filename or None,
                    business_account=conversation.business_account
                )
                messages_data = wa_res.get('messages', [])
                if messages_data:
                    whatsapp_msg_id = messages_data[0].get('id', '')

            if whatsapp_msg_id:
                message.whatsapp_message_id = whatsapp_msg_id
                message.save(update_fields=['whatsapp_message_id'])
        except Exception as exc:
            whatsapp_error_text = str(exc)
            message.status = Message.STATUS_FAILED
            message.save(update_fields=['status'])
            logger.error(f"Cloud API dispatch error: {exc}")

        # Human Handover: When human agent manually sends a message, pause active bot flow
        try:
            from .models import UserFlowSession
            active_sessions = UserFlowSession.objects.filter(
                conversation=conversation,
                status=UserFlowSession.STATUS_ACTIVE
            )
            if active_sessions.exists():
                active_sessions.update(
                    status=UserFlowSession.STATUS_HANDED_OVER,
                    handed_over_at=timezone.now(),
                    paused_at=timezone.now()
                )
                logger.info(f"Conversation {conversation.id} automation handed over to human agent.")
        except Exception as handover_err:
            logger.warning(f"Failed to flag session as handed over: {handover_err}")

        # Broadcast to conversation WebSocket room
        message_data = MessageSerializer(message, context={'request': request}).data
        if whatsapp_error_text:
            message_data['whatsapp_error'] = whatsapp_error_text

        broadcast_event(f"chat_{conversation.id}", {
            "type": "chat_message",
            "message": message_data
        })

        # Broadcast to global inbox room
        broadcast_event("inbox_updates", {
            "type": "conversation_update",
            "conversation": {
                "id": conversation.id,
                "business_account_id": conversation.business_account_id,
                "customer_name": conversation.customer_name,
                "phone_number": conversation.phone_number,
                "last_message": conversation.last_message,
                "last_message_time": conversation.display_time,
                "unread_count": conversation.unread_count,
            }
        })

        return Response(message_data, status=status.HTTP_201_CREATED)


class SearchAPI(APIView):
    """
    GET /api/search/?q=...&business_account_id=...
    Searches conversations by customer name, phone number, or message text.
    """
    def get(self, request):
        query = request.query_params.get('q', '').strip()
        business_account_id = request.query_params.get('business_account_id')
        queryset = crm.conversations_for_user(request.user, Conversation.objects.filter(is_archived=False))

        if business_account_id:
            queryset = queryset.filter(business_account_id=business_account_id)

        if query:
            queryset = queryset.filter(
                Q(customer_name__icontains=query) |
                Q(phone_number__icontains=query) |
                Q(last_message__icontains=query) |
                Q(messages__message_text__icontains=query)
            ).distinct()

        serializer = ConversationSerializer(queryset, many=True, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)


@method_decorator(csrf_exempt, name='dispatch')
class WhatsAppWebhookView(View):
    """
    GET  /webhook/whatsapp/ -> Meta Webhook Verification handshake
    POST /webhook/whatsapp/ -> Ingestion of incoming messages and status changes
    """

    def get(self, request):
        mode = request.GET.get('hub.mode')
        token = request.GET.get('hub.verify_token')
        challenge = request.GET.get('hub.challenge')

        verified_challenge = verify_webhook_token(mode, token, challenge)
        if verified_challenge:
            logger.info("WhatsApp Webhook successfully verified by Meta Graph API.")
            return HttpResponse(verified_challenge, content_type="text/plain", status=200)

        logger.warning(f"WhatsApp Webhook verification failed. Received mode={mode}, token={token}")
        return HttpResponse("Verification token mismatch", status=403)

    def post(self, request):
        try:
            payload = json.loads(request.body.decode('utf-8'))
        except Exception as exc:
            logger.error(f"Malformed webhook JSON: {exc}")
            return HttpResponse("Bad Request", status=400)

        entries = payload.get('entry', [])
        for entry in entries:
            changes = entry.get('changes', [])
            for change in changes:
                value = change.get('value', {})
                field = change.get('field', '')

                if field == 'messages':
                    # Incoming user messages
                    if 'messages' in value:
                        try:
                            process_incoming_message(value)
                        except Exception as exc:
                            logger.error(f"Error processing incoming message: {exc}", exc_info=True)

                    # Outbound status changes (sent, delivered, read, failed)
                    if 'statuses' in value:
                        for status_item in value.get('statuses', []):
                            try:
                                process_message_status(status_item)
                            except Exception as exc:
                                logger.error(f"Error processing message status: {exc}", exc_info=True)

        return HttpResponse("EVENT_RECEIVED", status=200)


class FlowBuilderView(AutomationPageMixin, View):
    """
    Renders the Visual No-Code Flow Builder interface (/automation/).
    """
    def get(self, request, pk=None):
        return render(request, 'chat/flow_builder.html')


class AutomationFlowListAPI(APIView):
    """
    GET /api/flows/?business_account_id=...
    POST /api/flows/ (Creates new draft flow)
    """
    def get(self, request):
        business_account_id = request.query_params.get('business_account_id')
        flows = AutomationFlow.objects.all()
        if business_account_id:
            flows = flows.filter(Q(business_account_id=business_account_id) | Q(business_account__isnull=True))

        # Auto-seed default flow if none exist
        if not flows.exists():
            from .automation.engine import AutomationEngine
            biz = BusinessAccount.objects.filter(pk=business_account_id).first() if business_account_id else None
            AutomationEngine.get_or_create_default_flow(biz)
            flows = AutomationFlow.objects.all()

        serializer = AutomationFlowSerializer(flows, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request):
        serializer = AutomationFlowSerializer(data=request.data)
        if serializer.is_valid():
            flow = serializer.save(status=AutomationFlow.STATUS_DRAFT)
            return Response(AutomationFlowSerializer(flow).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class AutomationFlowDetailAPI(APIView):
    """
    GET, PUT, PATCH, DELETE /api/flows/<id>/
    """
    def get(self, request, pk):
        flow = get_object_or_404(AutomationFlow, pk=pk)
        return Response(AutomationFlowSerializer(flow).data, status=status.HTTP_200_OK)

    def put(self, request, pk):
        flow = get_object_or_404(AutomationFlow, pk=pk)
        if flow.status == AutomationFlow.STATUS_PUBLISHED:
            return Response(
                {'error': 'Cannot modify published flow. Published flow versions are immutable. Create a new draft version to make changes.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        serializer = AutomationFlowSerializer(flow, data=request.data, partial=True)
        if serializer.is_valid():
            updated = serializer.save()
            return Response(AutomationFlowSerializer(updated).data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        flow = get_object_or_404(AutomationFlow, pk=pk)
        flow.delete()
        return Response({'message': 'Flow deleted successfully.'}, status=status.HTTP_200_OK)


class AutomationFlowPublishAPI(APIView):
    """
    POST /api/flows/<id>/publish/
    Validates graph, increments version, marks status as 'published', sets published_at = now().
    """
    def post(self, request, pk):
        flow = get_object_or_404(AutomationFlow, pk=pk)
        from .automation.validator import validate_flow_graph
        validation_res = validate_flow_graph(flow.flow_data or {})
        if not validation_res.get('valid'):
            return Response({
                'valid': False,
                'error': 'Validation failed.',
                'details': validation_res.get('errors', []),
                'errors': validation_res.get('errors', [])
            }, status=status.HTTP_400_BAD_REQUEST)

        if flow.version < 1:
            flow.version = 1
        flow.status = AutomationFlow.STATUS_PUBLISHED
        flow.published_at = timezone.now()
        flow.save(update_fields=['version', 'status', 'published_at'])
        return Response({
            'valid': True,
            'message': f'Flow "{flow.name}" successfully published as Version {flow.version}!',
            'flow': AutomationFlowSerializer(flow).data
        }, status=status.HTTP_200_OK)


class AutomationFlowCreateDraftAPI(APIView):
    """
    POST /api/flows/<id>/create-draft/
    Forks a published flow into a new editable draft.
    """
    def post(self, request, pk):
        source_flow = get_object_or_404(AutomationFlow, pk=pk)
        new_draft = AutomationFlow.objects.create(
            business_account=source_flow.business_account,
            name=source_flow.name,
            slug=source_flow.slug,
            version=source_flow.version + 1,
            status=AutomationFlow.STATUS_DRAFT,
            trigger_type=source_flow.trigger_type,
            trigger_keywords=source_flow.trigger_keywords,
            flow_data=source_flow.flow_data,
            is_active=True
        )
        data = AutomationFlowSerializer(new_draft).data
        return Response({'flow': data, **data}, status=status.HTTP_201_CREATED)


class ResumeAutomationAPI(APIView):
    """
    POST /api/conversations/<id>/resume-automation/
    Allows human agent to return bot control to active state.
    Continues from stored current_node_id; never re-executes trigger or greeting.
    """
    def post(self, request, pk):
        conversation = _conversation_or_403(request.user, pk)
        session = UserFlowSession.objects.filter(conversation=conversation).order_by('-started_at').first()
        if session:
            session.status = UserFlowSession.STATUS_ACTIVE
            session.paused_at = None
            session.handed_over_at = None
            session.save(update_fields=['status', 'paused_at', 'handed_over_at', 'updated_at'])
            return Response({
                'message': 'Automation resumed. Bot will continue from current step on next customer message.',
                'status': session.status,
                'current_node_id': session.current_node_id
            }, status=status.HTTP_200_OK)

        from .automation.engine import AutomationEngine
        flow = AutomationEngine.get_or_create_default_flow(conversation.business_account)
        new_session = UserFlowSession.objects.create(
            conversation=conversation,
            flow=flow,
            flow_version=flow.version,
            current_node_id=AutomationEngine.get_trigger_node_id(flow.flow_data),
            status=UserFlowSession.STATUS_ACTIVE
        )
        return Response({
            'message': 'New automation session initiated.',
            'status': new_session.status
        }, status=status.HTTP_201_CREATED)


class ValidateFlowAPI(APIView):
    """
    POST /api/flows/validate/
    POST /api/flows/<id>/validate/
    Validates a graph data structure before saving or publishing.
    """
    def post(self, request, pk=None):
        from .automation.validator import validate_flow_graph
        if pk:
            flow = get_object_or_404(AutomationFlow, pk=pk)
            flow_data = request.data.get('flow_data') or flow.flow_data or {}
        else:
            flow_data = request.data.get('flow_data', {})

        result = validate_flow_graph(flow_data)
        return Response(result, status=status.HTTP_200_OK if result.get('valid') else status.HTTP_400_BAD_REQUEST)


class AIFlowAssistantAPI(APIView):
    """
    POST /api/flows/generate-from-prompt/
    Interprets natural language prompts from users and builds a valid, structured
    n8n-style workflow graph with nodes, ports, and explicit edges.
    """
    def post(self, request):
        prompt = request.data.get('prompt', '').strip()
        if not prompt:
            return Response({'error': 'Please provide a workflow description.'}, status=status.HTTP_400_BAD_REQUEST)

        prompt_lower = prompt.lower()
        flow_name = request.data.get('name') or "AI Generated Workflow"

        nodes = []
        connections = []
        y_cursor = 40
        x_pos = 240
        prev_node_id = None
        edge_counter = 1

        # 1. Trigger Node (Always created)
        trigger_id = "trigger_1"
        is_keyword = any(k in prompt_lower for k in ['keyword', 'specific word', 'type '])
        trigger_node = {
            "id": trigger_id,
            "type": "trigger",
            "title": "Incoming WhatsApp Trigger",
            "position": {"x": x_pos, "y": y_cursor},
            "x": x_pos,
            "y": y_cursor,
            "data": {
                "trigger_type": "keyword" if is_keyword else "first_incoming_message"
            }
        }
        nodes.append(trigger_node)
        prev_node_id = trigger_id
        y_cursor += 160

        # Helper to link
        def connect_nodes(src_id, tgt_id, port="default"):
            nonlocal edge_counter
            connections.append({
                "id": f"edge_{edge_counter}",
                "source": src_id,
                "source_output": port,
                "target": tgt_id,
                "target_input": "input"
            })
            edge_counter += 1

        # 2. Greeting / Welcome Message
        msg_id = "greeting_1"
        greeting_text = "👋 Welcome to our WhatsApp service! We are happy to assist you today."
        if "lead" in prompt_lower or "course" in prompt_lower or "admission" in prompt_lower:
            greeting_text = "👋 Welcome to our Academy! We provide career-transforming technical training courses. Let's find the best fit for you! 🚀"
        elif "support" in prompt_lower or "help" in prompt_lower:
            greeting_text = "👋 Hello! Welcome to Customer Support. How can we assist you today?"

        nodes.append({
            "id": msg_id,
            "type": "message",
            "title": "Welcome Greeting",
            "body": greeting_text,
            "position": {"x": x_pos, "y": y_cursor},
            "x": x_pos,
            "y": y_cursor,
            "data": {"text": greeting_text}
        })
        connect_nodes(prev_node_id, msg_id)
        prev_node_id = msg_id
        y_cursor += 180

        # 3. Question (Name / Email / Requirement)
        if any(w in prompt_lower for w in ['name', 'who', 'ask name', 'student name']):
            q_name_id = "ask_name_1"
            nodes.append({
                "id": q_name_id,
                "type": "question",
                "title": "Ask Customer Name",
                "body": "Could you please tell us your *Full Name*?",
                "variable_name": "customer_name",
                "expected_type": "text",
                "retry_limit": 3,
                "position": {"x": x_pos, "y": y_cursor},
                "x": x_pos,
                "y": y_cursor,
                "data": {
                    "text": "Could you please tell us your *Full Name*?",
                    "variable_name": "customer_name",
                    "expected_type": "text",
                    "retry_limit": 3
                }
            })
            connect_nodes(prev_node_id, q_name_id)
            prev_node_id = q_name_id
            y_cursor += 180

        if any(w in prompt_lower for w in ['email', 'mail']):
            q_email_id = "ask_email_1"
            nodes.append({
                "id": q_email_id,
                "type": "question",
                "title": "Ask Email Address",
                "body": "Please provide your *Email Address* so we can send you updates and details:",
                "variable_name": "email",
                "expected_type": "email",
                "retry_limit": 3,
                "invalid_message": "⚠️ Please enter a valid email address (e.g. name@example.com):",
                "position": {"x": x_pos, "y": y_cursor},
                "x": x_pos,
                "y": y_cursor,
                "data": {
                    "text": "Please provide your *Email Address* so we can send you updates and details:",
                    "variable_name": "email",
                    "expected_type": "email",
                    "retry_limit": 3,
                    "invalid_message": "⚠️ Please enter a valid email address (e.g. name@example.com):"
                }
            })
            connect_nodes(prev_node_id, q_email_id)
            prev_node_id = q_email_id
            y_cursor += 180

        if any(w in prompt_lower for w in ['appointment', 'booking', 'slot', 'schedule', 'counseling', 'date', 'time']):
            slot_id = "appointment_slot_1"
            nodes.append({
                "id": slot_id,
                "type": "question",
                "title": "Preferred Appointment Slot",
                "body": "📅 What is your preferred *Date & Time* for the counseling session? (e.g. *Tomorrow 11 AM* or *Saturday 3 PM*):",
                "variable_name": "appointment_slot",
                "expected_type": "text",
                "retry_limit": 3,
                "position": {"x": x_pos, "y": y_cursor},
                "x": x_pos,
                "y": y_cursor,
                "data": {
                    "text": "📅 What is your preferred *Date & Time* for the counseling session? (e.g. *Tomorrow 11 AM* or *Saturday 3 PM*):",
                    "variable_name": "appointment_slot",
                    "expected_type": "text"
                }
            })
            connect_nodes(prev_node_id, slot_id)
            prev_node_id = slot_id
            y_cursor += 180

        # 4. Interactive Buttons or List
        if any(w in prompt_lower for w in ['course', 'training', 'catalog', 'programs', 'list']):
            list_id = "course_menu_1"
            nodes.append({
                "id": list_id,
                "type": "list",
                "title": "Course Menu",
                "body": "Please choose the technical program you are interested in:",
                "button_text": "View Programs",
                "source": "database",
                "variable_name": "course",
                "position": {"x": x_pos, "y": y_cursor},
                "x": x_pos,
                "y": y_cursor,
                "data": {
                    "text": "Please choose the technical program you are interested in:",
                    "button_text": "View Programs",
                    "source": "database",
                    "variable_name": "course"
                }
            })
            connect_nodes(prev_node_id, list_id)
            prev_node_id = list_id
            y_cursor += 180

        elif any(w in prompt_lower for w in ['choice', 'button', 'options', 'menu']):
            btn_id = "choice_buttons_1"
            opts = [
                {"id": "opt_general", "title": "General Info", "next_node_id": None},
                {"id": "opt_pricing", "title": "Pricing & Fees", "next_node_id": None},
                {"id": "opt_talk", "title": "Talk to Advisor", "next_node_id": None}
            ]
            nodes.append({
                "id": btn_id,
                "type": "buttons",
                "title": "Select Inquiry Type",
                "body": "How can we assist you today? Please tap an option below:",
                "variable_name": "inquiry_type",
                "options": opts,
                "position": {"x": x_pos, "y": y_cursor},
                "x": x_pos,
                "y": y_cursor,
                "data": {
                    "text": "How can we assist you today? Please tap an option below:",
                    "variable_name": "inquiry_type",
                    "options": opts
                }
            })
            connect_nodes(prev_node_id, btn_id)
            prev_node_id = btn_id
            y_cursor += 180

        # 5. Condition Branching (If mentioned)
        if any(w in prompt_lower for w in ['if', 'condition', 'branch', 'yes or no', 'visit']):
            cond_id = "condition_check_1"
            nodes.append({
                "id": cond_id,
                "type": "condition",
                "title": "Verify Requirement",
                "variable_name": "inquiry_type",
                "operator": "contains",
                "value": "Advisor",
                "position": {"x": x_pos, "y": y_cursor},
                "x": x_pos,
                "y": y_cursor,
                "data": {
                    "variable": "inquiry_type",
                    "operator": "contains",
                    "value": "Advisor"
                }
            })
            connect_nodes(prev_node_id, cond_id)
            y_cursor += 180

            # Handover for YES branch
            handover_id = "handover_yes_1"
            nodes.append({
                "id": handover_id,
                "type": "human_handover",
                "title": "Transfer to Representative",
                "body": "Connecting you with our senior representative right now... 👤",
                "position": {"x": x_pos + 160, "y": y_cursor},
                "x": x_pos + 160,
                "y": y_cursor,
                "data": {"text": "Connecting you with our senior representative right now... 👤"}
            })
            connect_nodes(cond_id, handover_id, "YES")

            # Continue for NO branch
            summary_id = "summary_no_1"
            nodes.append({
                "id": summary_id,
                "type": "message",
                "title": "Details Summary",
                "body": "Thank you for the information! Our automated guide has registered your interest.",
                "position": {"x": x_pos - 120, "y": y_cursor},
                "x": x_pos - 120,
                "y": y_cursor,
                "data": {"text": "Thank you for the information! Our automated guide has registered your interest."}
            })
            connect_nodes(cond_id, summary_id, "NO")
            prev_node_id = summary_id
            y_cursor += 180

        # 6. Brochure or Media (If mentioned)
        if any(w in prompt_lower for w in ['brochure', 'pdf', 'document', 'curriculum', 'syllabus']):
            brochure_id = "send_brochure_1"
            nodes.append({
                "id": brochure_id,
                "type": "media",
                "title": "Send Curriculum Brochure",
                "source": "selected_course_brochure",
                "caption": "📄 Here is your curriculum brochure and course details.",
                "position": {"x": x_pos, "y": y_cursor},
                "x": x_pos,
                "y": y_cursor,
                "data": {
                    "source": "selected_course_brochure",
                    "caption": "📄 Here is your curriculum brochure and course details."
                }
            })
            connect_nodes(prev_node_id, brochure_id)
            prev_node_id = brochure_id
            y_cursor += 180

        # 7. Location Pin (If mentioned)
        if any(w in prompt_lower for w in ['location', 'branch', 'address', 'map', 'center']):
            loc_id = "send_location_1"
            nodes.append({
                "id": loc_id,
                "type": "location",
                "title": "Send Branch Location",
                "source": "dynamic_branch",
                "position": {"x": x_pos, "y": y_cursor},
                "x": x_pos,
                "y": y_cursor,
                "data": {"source": "dynamic_branch"}
            })
            connect_nodes(prev_node_id, loc_id)
            prev_node_id = loc_id
            y_cursor += 180

        # 8. Human Handover (If specifically requested and not already added)
        if any(w in prompt_lower for w in ['handover', 'agent', 'human', 'representative', 'support agent']) and not any(n['type'] == 'human_handover' for n in nodes):
            handover_id = "human_handover_1"
            nodes.append({
                "id": handover_id,
                "type": "human_handover",
                "title": "Handover to Human Agent",
                "body": "Connecting you with an agent now. Please hold on! 👤",
                "position": {"x": x_pos, "y": y_cursor},
                "x": x_pos,
                "y": y_cursor,
                "data": {"text": "Connecting you with an agent now. Please hold on! 👤"}
            })
            connect_nodes(prev_node_id, handover_id)
            prev_node_id = handover_id
            y_cursor += 180

        # 9. Terminal End Node (Always created)
        end_id = "end_1"
        nodes.append({
            "id": end_id,
            "type": "end",
            "title": "Session Completed",
            "body": "Thank you for reaching out! Feel free to message us again anytime. Have a great day! 🌟",
            "position": {"x": x_pos, "y": y_cursor},
            "x": x_pos,
            "y": y_cursor,
            "data": {
                "text": "Thank you for reaching out! Feel free to message us again anytime. Have a great day! 🌟"
            }
        })
        connect_nodes(prev_node_id, end_id)

        # Connect any loose handover nodes to end as well
        for n in nodes:
            if n['type'] == 'human_handover':
                if not any(c['source'] == n['id'] for c in connections):
                    connect_nodes(n['id'], end_id)

        draft_flow_data = {
            "nodes": nodes,
            "connections": connections,
            "settings": {
                "session_timeout_hours": 24,
                "handover_keywords": ["agent", "human", "support", "help"]
            }
        }

        return Response({
            "success": True,
            "flow_name": flow_name,
            "flow_data": draft_flow_data,
            "flow": {
                "id": None,
                "name": flow_name,
                "slug": slugify(flow_name),
                "trigger_type": "keyword",
                "trigger_keywords": "hi, hello, start",
                "version": 1,
                "status": "draft",
                "flow_data": draft_flow_data
            },
            "node_count": len(nodes),
            "connection_count": len(connections),
            "message": f"Successfully generated workflow '{flow_name}' with {len(nodes)} steps and {len(connections)} connections."
        }, status=status.HTTP_200_OK)




# Inbox APIs: any logged-in CRM user (results are scoped per user above).
for _view in (BusinessAccountListAPI, ConversationListAPI, ConversationMessagesAPI, SendMessageAPI, SearchAPI,
              ResumeAutomationAPI):
    _view.permission_classes = [IsInboxUser]

# Automation + WhatsApp number management: Admin and Sales Head only.
for _view in (BusinessAccountDetailAPI, AutomationFlowListAPI, AutomationFlowDetailAPI, AutomationFlowPublishAPI,
              AutomationFlowCreateDraftAPI, ValidateFlowAPI, AIFlowAssistantAPI):
    _view.permission_classes = [CanManageAutomation]


class CRMOptionsAPI(APIView):
    """GET /api/crm/options/ - dropdowns for the flow builder's Lead Status / Assign Telecaller steps."""
    permission_classes = [CanManageAutomation]

    def get(self, request):
        from accounts.models import User
        from leads.models import LeadStatus
        telecallers = User.get_telecallers_queryset().select_related('branch').order_by('-is_active', 'first_name', 'username')
        return Response({
            'statuses': [{'value': v, 'label': l} for v, l in LeadStatus.choices],
            'telecallers': [
                {'id': t.pk, 'name': (t.get_full_name() or t.username) + (f" ({t.branch.name})" if t.branch else ''),
                 'is_active': t.is_active}
                for t in telecallers
            ],
        })


# ==========================================
# TELECALLER WHATSAPP MESSAGING & VOICE (REQ 3 & 15)
# ==========================================

from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
import json

@login_required
def api_telecaller_send_whatsapp(request, lead_id):
    """
    POST /chat/api/leads/<lead_id>/send-whatsapp/
    Sends 1-to-1 WhatsApp messages (custom or template) to a lead directly from CRM.
    Logs message in WhatsApp Conversation and Activity history.
    """
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'POST method required.'}, status=405)

    from leads.models import Lead
    from accounts.permissions import can_access_lead
    from activities.utils import log_activity
    from .whatsapp.webhook import format_phone_e164
    from .whatsapp.messages import send_text_message

    lead = get_object_or_404(Lead, pk=lead_id)
    if not can_access_lead(request.user, lead):
        return JsonResponse({'success': False, 'error': 'Permission denied for this lead.'}, status=403)

    try:
        try:
            data = json.loads(request.body)
        except Exception:
            data = request.POST

        template_key = data.get('template_key', 'custom').strip()
        custom_text = data.get('message_text', '').strip()

        preset_templates = {
            'welcome': f"Hello {lead.name}, welcome to TECHPANDA! Thank you for inquiring about our programs. How can we assist you with your career goals today?",
            'followup': f"Hi {lead.name}, following up on our previous conversation regarding your course inquiry at TECHPANDA. Are you available for a brief discussion today?",
            'course_details': f"Hello {lead.name}, here are the comprehensive details for our training & placement programs at TECHPANDA. We offer industry-standard curriculum and hands-on projects.",
            'brochure': f"Hi {lead.name}, please find our latest course catalog and syllabus overview. Feel free to reply here if you have any questions!",
        }

        if template_key in preset_templates:
            body_text = preset_templates[template_key]
        elif custom_text:
            body_text = custom_text
        else:
            return JsonResponse({'success': False, 'error': 'Message text or valid template is required.'}, status=400)

        clean_phone = format_phone_e164(lead.phone)
        if not clean_phone:
            return JsonResponse({'success': False, 'error': 'Lead has an invalid or missing phone number.'}, status=400)

        # Select business account matching lead's branch or default
        biz_account = None
        if lead.branch_id:
            biz_account = BusinessAccount.objects.filter(crm_branch_id=lead.branch_id, is_active=True).first()
        if not biz_account:
            biz_account = BusinessAccount.objects.filter(is_default=True, is_active=True).first() or BusinessAccount.objects.filter(is_active=True).first()

        # Get or create conversation
        conversation, _ = Conversation.objects.get_or_create(
            business_account=biz_account,
            phone_number=clean_phone,
            defaults={'customer_name': lead.name}
        )

        # Record outbound message in CRM chat history
        message = Message.objects.create(
            conversation=conversation,
            sender=Message.SENDER_AGENT,
            message_type=Message.TYPE_TEXT,
            message_text=body_text,
            status=Message.STATUS_SENT
        )

        conversation.last_message = body_text
        conversation.last_message_time = timezone.now()
        conversation.save(update_fields=['last_message', 'last_message_time', 'updated_at'])

        # Dispatch via Meta Cloud API if configured
        dispatch_status = 'logged_locally'
        try:
            from .whatsapp.client import WhatsAppClient
            client = WhatsAppClient(business_account=biz_account)
            if client.is_configured:
                api_res = send_text_message(clean_phone, body_text, business_account=biz_account)
                dispatch_status = 'dispatched_meta_api'
        except Exception as api_err:
            logger.warning(f"Meta Cloud API send skipped or failed: {api_err}")

        # Log Activity
        log_activity(
            user=request.user,
            action="WhatsApp Message Sent",
            description=f"Sent WhatsApp message ({template_key}) to '{lead.name}': \"{body_text[:60]}...\"",
            object_type="Lead",
            object_id=lead.id,
            request=request
        )

        return JsonResponse({
            'success': True,
            'message_id': message.id,
            'conversation_id': conversation.id,
            'text': body_text,
            'dispatch_status': dispatch_status,
            'recipient': clean_phone,
        })
    except Exception as e:
        logger.exception("Failed to send WhatsApp message: %s", e)
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
def api_whatsapp_voice_capability(request, lead_id):
    """
    GET /chat/api/leads/<lead_id>/voice-capability/
    Verifies WhatsApp voice calling capability for the lead.
    Returns status, prerequisites, and fallback dialing parameters.
    """
    from django.conf import settings
    from leads.models import Lead
    from accounts.permissions import can_access_lead
    from .whatsapp.webhook import format_phone_e164

    lead = get_object_or_404(Lead, pk=lead_id)
    if not can_access_lead(request.user, lead):
        return JsonResponse({'success': False, 'error': 'Permission denied.'}, status=403)

    clean_phone = format_phone_e164(lead.phone)
    raw_phone = ''.join(c for c in lead.phone if c.isdigit())

    # Check Meta Voice Calling capability prerequisites
    meta_voice_configured = bool(getattr(settings, 'WHATSAPP_VOICE_SIP_ENABLED', False))

    return JsonResponse({
        'success': True,
        'capability': 'whatsapp_voice_calling',
        'is_configured': meta_voice_configured,
        'status': 'configured' if meta_voice_configured else 'prerequisites_required',
        'lead_name': lead.name,
        'phone': lead.phone,
        'clean_phone': clean_phone,
        'wa_call_url': f"https://wa.me/{raw_phone}",
        'tel_url': f"tel:{lead.phone}",
        'prerequisites': [
            'Meta WhatsApp Business Calling API permission approved',
            'Registered Cloud API phone number with 2-way Voice enabled',
            'Configured SIP Trunk / WebRTC Voice Gateway (Twilio/Asterisk)',
            'Inbound & Outbound Calling rules assigned in WhatsApp Manager'
        ],
        'recommended_action': 'tel_dial' if not meta_voice_configured else 'meta_voip'
    })

