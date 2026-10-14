"""
Django Channels WebSocket Consumers for Real-Time WhatsApp CRM.
Supports per-conversation messaging rooms and global inbox state updates.
"""

import json
import logging
from channels.generic.websocket import AsyncWebsocketConsumer

logger = logging.getLogger(__name__)


class ChatConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for an active conversation chat room (/ws/chat/<conversation_id>/).
    """

    async def connect(self):
        self.conversation_id = self.scope['url_route']['kwargs']['conversation_id']
        self.room_group_name = f"chat_{self.conversation_id}"

        # Join conversation group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        await self.accept()

    async def disconnect(self, close_code):
        # Leave conversation group
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    async def receive(self, text_data=None, bytes_data=None):
        """
        Receives messages from WebSocket client (e.g. typing indicators or client heartbeat).
        """
        if not text_data:
            return
        try:
            data = json.loads(text_data)
            msg_type = data.get('type')

            if msg_type == 'ping':
                await self.send(text_data=json.dumps({'type': 'pong'}))
            elif msg_type == 'typing':
                # Broadcast typing notification to the room
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        'type': 'chat_typing',
                        'is_typing': data.get('is_typing', True),
                        'sender': data.get('sender', 'agent'),
                    }
                )
        except Exception as exc:
            logger.warning(f"Error handling WebSocket message: {exc}")

    async def chat_message(self, event):
        """Dispatches an incoming or outgoing chat message to the client."""
        await self.send(text_data=json.dumps({
            'type': 'message',
            'message': event['message']
        }))

    async def message_status_update(self, event):
        """Dispatches a message delivery/read status update."""
        await self.send(text_data=json.dumps({
            'type': 'status_update',
            'message_id': event['message_id'],
            'whatsapp_message_id': event.get('whatsapp_message_id'),
            'status': event['status']
        }))

    async def chat_typing(self, event):
        """Dispatches typing indicators."""
        await self.send(text_data=json.dumps({
            'type': 'typing',
            'is_typing': event['is_typing'],
            'sender': event['sender'],
        }))


class InboxConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for global inbox updates (/ws/inbox/).
    Updates unread counts, last messages, and conversation ordering across all chats.
    """

    async def connect(self):
        self.group_name = "inbox_updates"
        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name
        )
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            self.group_name,
            self.channel_name
        )

    async def conversation_update(self, event):
        """Dispatches updated preview info for a conversation item."""
        await self.send(text_data=json.dumps({
            'type': 'conversation_update',
            'conversation': event['conversation']
        }))
