"""
WhatsApp Cloud API Webhook Processing.
Handles verification handshake, incoming messages, and message status callbacks.
"""

import logging
from datetime import datetime
from typing import Optional, Dict, Any
from django.conf import settings
from django.utils import timezone
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from chat.models import Conversation, Message

logger = logging.getLogger(__name__)


def verify_webhook_token(mode: Optional[str], token: Optional[str], challenge: Optional[str]) -> Optional[str]:
    """
    Verifies the webhook subscription handshake requested by Meta Graph API.
    """
    expected_token = getattr(settings, 'WHATSAPP_VERIFY_TOKEN', '')
    if mode == 'subscribe' and token and token == expected_token:
        return challenge
    return None


def format_phone_e164(phone: str) -> str:
    """Ensure phone number has leading plus and contains only digits."""
    digits = ''.join(c for c in str(phone) if c.isdigit())
    return f"+{digits}" if digits else ""


def broadcast_to_channel(group_name: str, event_data: dict):
    """Safely broadcasts a message event to Django Channels layer if active."""
    try:
        channel_layer = get_channel_layer()
        if channel_layer:
            async_to_sync(channel_layer.group_send)(
                group_name,
                event_data
            )
    except Exception as exc:
        logger.warning(f"Could not broadcast to channel group {group_name}: {exc}")


def process_incoming_message(value: Dict[str, Any], default_business_account: Optional[Any] = None) -> None:
    """
    Processes an incoming WhatsApp message from the webhook payload.
    Creates or updates the Conversation linked to the Business Account.
    """
    metadata = value.get('metadata', {})
    business_phone_number_id = metadata.get('phone_number_id', '')
    display_phone_number = metadata.get('display_phone_number', '')

    business_account = default_business_account
    if not business_account and business_phone_number_id:
        from chat.models import BusinessAccount
        formatted_display = format_phone_e164(display_phone_number) if display_phone_number else business_phone_number_id
        business_account = BusinessAccount.objects.filter(phone_number_id=business_phone_number_id).first()
        if not business_account:
            business_account = BusinessAccount.objects.create(
                name=f"Line ({formatted_display})",
                phone_number=formatted_display,
                phone_number_id=business_phone_number_id,
                is_active=True,
            )

    contacts = value.get('contacts', [])
    messages = value.get('messages', [])

    if not messages:
        return

    contact_map = {}
    for c in contacts:
        contact_map[c.get('wa_id')] = c.get('profile', {}).get('name', '')

    for msg in messages:
        sender_wa_id = msg.get('from', '')
        if not sender_wa_id:
            continue

        raw_phone = format_phone_e164(sender_wa_id)
        customer_name = contact_map.get(sender_wa_id) or raw_phone
        wamid = msg.get('id', '')

        # Avoid duplicate ingestion
        if wamid and Message.objects.filter(whatsapp_message_id=wamid).exists():
            logger.info(f"Message {wamid} already ingested; skipping.")
            continue

        # Get or create conversation scoped to business_account
        conversation, created = Conversation.objects.get_or_create(
            business_account=business_account,
            phone_number=raw_phone,
            defaults={
                'customer_name': customer_name,
                'is_online': True,
                'last_seen': 'online',
            }
        )

        if not created and customer_name and conversation.customer_name == raw_phone:
            conversation.customer_name = customer_name

        # CRM: every WhatsApp contact is a lead (source WhatsApp), one lead per phone number.
        # A CRM problem must never stop the message from being saved.
        try:
            from chat.crm import ensure_lead_for_conversation
            ensure_lead_for_conversation(conversation, conversation_created=created)
        except Exception as lead_exc:
            logger.error(f"CRM lead sync failed for {raw_phone}: {lead_exc}", exc_info=True)

        # Parse message content (including interactive buttons and list selections)
        msg_type = msg.get('type', 'text')
        text_content = ''
        interactive_info = {}

        if msg_type == 'text':
            text_content = msg.get('text', {}).get('body', '')
        elif msg_type == 'interactive':
            interactive = msg.get('interactive', {})
            itype = interactive.get('type')
            if itype == 'button_reply':
                btn = interactive.get('button_reply', {})
                text_content = btn.get('title', '')
                interactive_info = {'type': 'button_reply', 'button_reply': btn}
            elif itype == 'list_reply':
                lst = interactive.get('list_reply', {})
                text_content = lst.get('title', '')
                interactive_info = {'type': 'list_reply', 'list_reply': lst}
            else:
                text_content = '[Interactive Selection]'
            msg_type = 'text'
        elif msg_type in ['image', 'video', 'audio', 'document']:
            media_info = msg.get(msg_type, {})
            text_content = media_info.get('caption', '') or f"[{msg_type.title()}]"
        else:
            text_content = f"[{msg_type.title()} message]"

        # Parse timestamp
        raw_ts = msg.get('timestamp')
        if raw_ts:
            try:
                msg_time = datetime.fromtimestamp(int(raw_ts), tz=timezone.utc)
            except Exception:
                msg_time = timezone.now()
        else:
            msg_time = timezone.now()

        # Save message with transaction safety
        from django.db import transaction, IntegrityError
        try:
            with transaction.atomic():
                if wamid and Message.objects.filter(whatsapp_message_id=wamid).exists():
                    logger.info(f"Duplicate WhatsApp message ID {wamid} detected inside transaction. Stopping.")
                    continue

                message = Message.objects.create(
                    conversation=conversation,
                    sender=Message.SENDER_CUSTOMER,
                    message_type=msg_type,
                    message_text=text_content,
                    whatsapp_message_id=wamid,
                    status=Message.STATUS_DELIVERED,
                    timestamp=msg_time
                )
        except IntegrityError:
            logger.info(f"Integrity error for duplicate message ID {wamid}. Skipping.")
            continue

        # Update conversation meta
        conversation.last_message = text_content
        conversation.last_message_time = msg_time
        conversation.unread_count += 1
        conversation.is_online = True
        conversation.last_seen = 'online'
        conversation.save(update_fields=[
            'last_message',
            'last_message_time',
            'unread_count',
            'is_online',
            'last_seen',
            'updated_at'
        ])

        # Real-time WebSocket broadcasts
        msg_payload = {
            "type": "chat_message",
            "message": {
                "id": message.id,
                "conversation_id": conversation.id,
                "sender": message.sender,
                "message_type": message.message_type,
                "message_text": message.message_text,
                "media_url": None,
                "whatsapp_message_id": message.whatsapp_message_id,
                "status": message.status,
                "timestamp": message.timestamp.isoformat(),
                "display_time": message.display_time,
            }
        }
        # Notify specific chat room
        broadcast_to_channel(f"chat_{conversation.id}", msg_payload)
        # Notify conversation list
        broadcast_to_channel("inbox_updates", {
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

        # -------------------------------------------------------------
        # WhatsApp Automation Engine Evaluation
        # -------------------------------------------------------------
        try:
            from chat.automation.engine import AutomationEngine
            AutomationEngine.process_incoming(conversation, text_content, incoming_data=interactive_info)
        except Exception as auto_exc:
            logger.error(f"Error in AutomationEngine for conv {conversation.id}: {auto_exc}", exc_info=True)


def process_message_status(status_item: Dict[str, Any]) -> None:
    """
    Updates the delivery/read status of an outbound message in SQLite.
    Status values: 'sent', 'delivered', 'read', 'failed'
    """
    wamid = status_item.get('id')
    new_status = status_item.get('status')

    if not wamid or not new_status:
        return

    valid_statuses = dict(Message.STATUS_CHOICES).keys()
    if new_status not in valid_statuses:
        logger.warning(f"Unrecognized WhatsApp status '{new_status}' received.")
        return

    updated_count = Message.objects.filter(whatsapp_message_id=wamid).update(status=new_status)
    if updated_count:
        msg = Message.objects.filter(whatsapp_message_id=wamid).first()
        if msg:
            broadcast_to_channel(f"chat_{msg.conversation_id}", {
                "type": "message_status_update",
                "message_id": msg.id,
                "whatsapp_message_id": wamid,
                "status": new_status,
            })

    try:
        from chat.campaign_service import update_recipient_from_webhook_status
        errors = status_item.get('errors', [{}])
        err_info = errors[0] if errors else None
        update_recipient_from_webhook_status(wamid, new_status, error_details=err_info)
    except Exception as camp_exc:
        logger.warning(f"Campaign status webhook update error for {wamid}: {camp_exc}")


def handle_incoming_webhook_message(msg_or_value: Dict[str, Any], business_account: Optional[Any] = None) -> None:
    """
    Standard interface for handling webhook message payloads or individual message dicts.
    """
    if 'messages' in msg_or_value:
        process_incoming_message(msg_or_value, default_business_account=business_account)
    else:
        fake_value = {
            'metadata': {'phone_number_id': business_account.phone_number_id if business_account else ''},
            'messages': [msg_or_value],
            'contacts': [{'wa_id': msg_or_value.get('from', ''), 'profile': {'name': ''}}]
        }
        process_incoming_message(fake_value, default_business_account=business_account)
