import json
import logging
from channels.generic.websocket import AsyncWebsocketConsumer
from asgiref.sync import sync_to_async
from .models import Room, Message

logger = logging.getLogger('chat')


class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.room_id = self.scope['url_route']['kwargs']['room_id']
        self.group_name = f'room_{self.room_id}'

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        # log origin header if present to diagnose origin issues
        origin = None
        try:
            for (k, v) in self.scope.get('headers', []):
                if k == b'origin':
                    origin = v.decode()
                    break
        except Exception:
            origin = None
        logger.info(f"WebSocket connected: {self.channel_name} room={self.room_id} origin={origin}")

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)
        logger.info(f"WebSocket disconnected: {self.channel_name} room={self.room_id} code={close_code}")

    async def receive(self, text_data=None, bytes_data=None):
        try:
            data = json.loads(text_data)
        except Exception:
            return
        user = data.get('user') or data.get('user_name') or 'anonymous'
        user_id = data.get('user_id') or data.get('userId')
        content = data.get('content') or data.get('text') or ''

        # Save to DB: ensure we fetch/create room, then create message with room instance
        room_obj_tuple = await sync_to_async(Room.objects.get_or_create)(id=self.room_id, defaults={'name': f'Room {self.room_id}'})
        room_obj = room_obj_tuple[0]
        user_obj = None
        if user_id:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            try:
                user_obj = await sync_to_async(User.objects.get)(id=user_id)
            except Exception:
                user_obj = None
        message = await sync_to_async(Message.objects.create)(
            room=room_obj,
            user_name=user,
            user=user_obj,
            content=content,
        )

        # Broadcast
        payload = {
            'id': message.id,
            'user_name': message.user_name,
            'user_id': message.user.id if message.user else None,
            'content': message.content,
            'created_at': message.created_at.isoformat(),
        }

        await self.channel_layer.group_send(
            self.group_name,
            {'type': 'chat.message', 'message': payload},
        )

    async def chat_message(self, event):
        message = event['message']
        await self.send(text_data=json.dumps(message))
