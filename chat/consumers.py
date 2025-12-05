import json
import logging
import asyncio
from channels.generic.websocket import AsyncWebsocketConsumer
from asgiref.sync import sync_to_async
from .models import Room, Message
from django.core.cache import cache
from datetime import datetime, timedelta

logger = logging.getLogger('chat')

# In-memory storage for online users per room (room_id -> set of user_ids)
# For production with multiple servers, use Redis instead
ONLINE_USERS = {}


class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.room_id = self.scope['url_route']['kwargs']['room_id']
        self.group_name = f'room_{self.room_id}' 
        self.presence_group = f'presence_{self.room_id}'
        self.user_id = None
        self.user_name = None
        
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.channel_layer.group_add(self.presence_group, self.channel_name)
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
        # Remove user from online users when they disconnect
        if self.user_id:
            await self.remove_user_from_presence()
        
        await self.channel_layer.group_discard(self.group_name, self.channel_name)
        await self.channel_layer.group_discard(self.presence_group, self.channel_name)
        logger.info(f"WebSocket disconnected: {self.channel_name} room={self.room_id} code={close_code}")

    async def receive(self, text_data=None, bytes_data=None):
        try:
            data = json.loads(text_data)
        except Exception:
            return
        
        message_type = data.get('type')
        
        # Handle ping/pong for keepalive
        if message_type == 'ping':
            await self.send(text_data=json.dumps({'type': 'pong'}))
            return
        
        # Handle user presence announcement (when user first connects)
        if message_type == 'user_connected':
            user_id = data.get('user_id')
            user_name = data.get('user_name') or data.get('user') or 'Anonymous'
            if user_id:
                self.user_id = str(user_id)
                self.user_name = user_name
                await self.add_user_to_presence()
            return
        
        # Handle heartbeat to keep user online
        if message_type == 'heartbeat':
            if self.user_id:
                await self.update_user_heartbeat()
            return
            
        user = data.get('user') or data.get('user_name') or 'anonymous'
        user_id = data.get('user_id') or data.get('userId')
        content = data.get('content') or data.get('text') or ''
        
        # If this is the first message from this user, track their presence
        if user_id and not self.user_id:
            self.user_id = str(user_id)
            self.user_name = user
            await self.add_user_to_presence()

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

        # Broadcast message
        payload = {
            'type': 'message',
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
        """Handle incoming chat messages"""
        message = event['message']
        await self.send(text_data=json.dumps(message))
    
    async def presence_update(self, event):
        """Handle presence update events"""
        await self.send(text_data=json.dumps(event['data']))
    
    async def add_user_to_presence(self):
        """Add user to online users list and broadcast join event"""
        if not self.user_id:
            return
            
        # Add to online users set
        if self.room_id not in ONLINE_USERS:
            ONLINE_USERS[self.room_id] = {}
        
        ONLINE_USERS[self.room_id][self.user_id] = {
            'user_name': self.user_name,
            'last_seen': datetime.now().isoformat()
        }
        
        # Get current online user IDs
        online_user_ids = list(ONLINE_USERS[self.room_id].keys())
        
        logger.info(f"User {self.user_id} ({self.user_name}) joined room {self.room_id}. Online: {online_user_ids}")
        
        # Broadcast presence update to all users in the room
        await self.channel_layer.group_send(
            self.presence_group,
            {
                'type': 'presence.update',
                'data': {
                    'type': 'presence_update',
                    'event': 'user_joined',
                    'user_id': self.user_id,
                    'user_name': self.user_name,
                    'online_users': online_user_ids,
                    'timestamp': datetime.now().isoformat()
                }
            }
        )
    
    async def remove_user_from_presence(self):
        """Remove user from online users list and broadcast leave event"""
        if not self.user_id or self.room_id not in ONLINE_USERS:
            return
        
        # Remove from online users
        if self.user_id in ONLINE_USERS[self.room_id]:
            del ONLINE_USERS[self.room_id][self.user_id]
        
        # Clean up empty room
        if not ONLINE_USERS[self.room_id]:
            del ONLINE_USERS[self.room_id]
        
        # Get remaining online user IDs
        online_user_ids = list(ONLINE_USERS.get(self.room_id, {}).keys())
        
        logger.info(f"User {self.user_id} ({self.user_name}) left room {self.room_id}. Online: {online_user_ids}")
        
        # Broadcast presence update
        await self.channel_layer.group_send(
            self.presence_group,
            {
                'type': 'presence.update',
                'data': {
                    'type': 'presence_update',
                    'event': 'user_left',
                    'user_id': self.user_id,
                    'user_name': self.user_name,
                    'online_users': online_user_ids,
                    'timestamp': datetime.now().isoformat()
                }
            }
        )
    
    async def update_user_heartbeat(self):
        """Update user's last seen timestamp"""
        if not self.user_id or self.room_id not in ONLINE_USERS:
            return
        
        if self.user_id in ONLINE_USERS[self.room_id]:
            ONLINE_USERS[self.room_id][self.user_id]['last_seen'] = datetime.now().isoformat()
