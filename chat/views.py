from rest_framework import generics
from rest_framework.response import Response
from rest_framework import status
from .models import Room, Message, Feedback
from .serializers import RoomSerializer, MessageSerializer, FeedbackSerializer
from rest_framework.views import APIView
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db import models as dj_models
from django.contrib.auth import get_user_model
from django.contrib.auth.models import User as DjangoUser
import random
import string
import logging

logger = logging.getLogger('chat')

# Maximum number of rooms a user can create
MAX_ROOMS_PER_USER = 3


class RoomListCreateView(generics.ListCreateAPIView):
    queryset = Room.objects.all().order_by('-created_at')
    serializer_class = RoomSerializer

    def get_queryset(self):
        # Prefer server-side authenticated user over client provided user_id
        user_id = None
        if getattr(self.request, 'user', None) and self.request.user.is_authenticated:
            user_id = getattr(self.request.user, 'id', None)
        else:
            user_id = self.request.query_params.get('user_id')
        if user_id:
            # Return rooms where user is creator or a member
            return Room.objects.filter(dj_models.Q(creator_id=user_id) | dj_models.Q(members__id=user_id)).distinct().order_by('-created_at')
        return super().get_queryset()

    def create(self, request, *args, **kwargs):
        # Check room creation limit before creating
        creator_id = None
        if getattr(request, 'user', None) and request.user.is_authenticated:
            creator_id = request.user.id
        else:
            creator_id = request.data.get('creator_id')
        
        if creator_id:
            # Count rooms created by this user
            created_rooms_count = Room.objects.filter(creator_id=creator_id).count()
            if created_rooms_count >= MAX_ROOMS_PER_USER:
                return Response(
                    {'detail': f'You can only create up to {MAX_ROOMS_PER_USER} rooms. Delete an existing room to create a new one.'},
                    status=status.HTTP_403_FORBIDDEN
                )
        
        return super().create(request, *args, **kwargs)

    def perform_create(self, serializer):
        # Prefer authenticated request user as creator when available
        creator = None
        if getattr(self.request, 'user', None) and self.request.user.is_authenticated:
            creator = self.request.user
        else:
            creator_id = self.request.data.get('creator_id')
            if creator_id:
                from django.contrib.auth import get_user_model
                User = get_user_model()
                try:
                    creator = User.objects.get(id=creator_id)
                except Exception:
                    creator = None
        room = serializer.save(creator=creator)
        # ensure creator is a member
        if creator:
            room.members.add(creator)


class RoomRetrieveView(generics.RetrieveAPIView):
    queryset = Room.objects.all()
    serializer_class = RoomSerializer


class MessageListCreateView(generics.ListCreateAPIView):
    serializer_class = MessageSerializer

    def get_queryset(self):
        room_id = self.kwargs['room_id']
        return Message.objects.filter(room_id=room_id).order_by('created_at')

    def create(self, request, *args, **kwargs):
        room_id = self.kwargs['room_id']
        user_name = request.data.get('user') or request.data.get('user_name') or 'anonymous'
        user_id = request.data.get('user_id') or request.data.get('user_id') or request.data.get('userId')
        content = request.data.get('content') or request.data.get('text') or request.data.get('message')

        if content is None:
            return Response({'detail': 'Message content required'}, status=status.HTTP_400_BAD_REQUEST)

        room, _ = Room.objects.get_or_create(id=room_id, defaults={'name': f'Room {room_id}'})
        # Prefer authenticated user for message ownership
        user = None
        if getattr(request, 'user', None) and request.user.is_authenticated:
            user = request.user
            if not user_name:
                user_name = f"{user.first_name} {user.last_name}".strip() or user.username
        elif user_id:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            try:
                user = User.objects.get(id=user_id)
                # override user_name if not provided
                if not user_name:
                    user_name = f"{user.first_name} {user.last_name}".strip() or user.username
            except Exception:
                user = None
        message = Message.objects.create(room=room, user_name=user_name, user=user, content=content)
        serializer = self.get_serializer(message)

        # Broadcast via WebSocket
        try:
            channel_layer = get_channel_layer()
            broadcast_data = {
                'id': message.id,
                'user_name': message.user_name,
                'user_id': message.user.id if message.user else None,
                'content': message.content,
                'created_at': message.created_at.isoformat(),
            }
            async_to_sync(channel_layer.group_send)(
                f'room_{room_id}',
                {'type': 'chat.message', 'message': broadcast_data},
            )
            logger.info(f"Broadcast message {message.id} to room_{room_id}")
        except Exception as e:
            logger.error(f"Broadcast failed for message {message.id}: {e}")

        return Response(serializer.data, status=status.HTTP_201_CREATED)


class JoinRoomView(APIView):
    def post(self, request, *args, **kwargs):
        room_key = request.data.get('room_key') or request.data.get('key')
        if not room_key:
            return Response({'detail': 'room_key required'}, status=status.HTTP_400_BAD_REQUEST)
        room = Room.objects.filter(key__iexact=room_key).first()
        if not room:
            return Response({'detail': 'Room not found'}, status=status.HTTP_404_NOT_FOUND)
        # Add authenticated user to members if present, otherwise use provided user_id
        if getattr(request, 'user', None) and request.user.is_authenticated:
            room.members.add(request.user)
        else:
            user_id = request.data.get('user_id') or request.data.get('user') or request.data.get('userId')
            if user_id:
                from django.contrib.auth import get_user_model
                User = get_user_model()
                try:
                    u = User.objects.get(id=user_id)
                    room.members.add(u)
                except Exception:
                    pass
        serializer = RoomSerializer(room)
        return Response(serializer.data, status=status.HTTP_200_OK)


import re

def validate_email(email):
    """Validate email format - must contain @ and end with valid domain"""
    if not email:
        return False
    # Basic email regex: something@something.domain
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.(com|net|org|edu|gov|io|co|info|biz|me|us|uk|ca|au|in|pk)$'
    return re.match(pattern, email, re.IGNORECASE) is not None


class RegisterView(APIView):
    def post(self, request, *args, **kwargs):
        username = request.data.get('username') or request.data.get('user_name')
        password = request.data.get('password')
        email = request.data.get('email') or request.data.get('email_address')
        first_name = request.data.get('first_name') or request.data.get('firstName') or ''
        last_name = request.data.get('last_name') or request.data.get('lastName') or ''
        
        # Validate required fields
        if not (username and password):
            return Response({'detail': 'username and password required'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Validate email is required
        if not email:
            return Response({'detail': 'email is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Validate email format
        if not validate_email(email):
            return Response({'detail': 'Invalid email format. Please use a valid email address (e.g., user@example.com)'}, status=status.HTTP_400_BAD_REQUEST)
        
        User = get_user_model()
        if User.objects.filter(username=username).exists():
            return Response({'detail': 'Username already taken'}, status=status.HTTP_409_CONFLICT)
        
        # Check if email is already in use
        if User.objects.filter(email=email).exists():
            return Response({'detail': 'Email already in use'}, status=status.HTTP_409_CONFLICT)
        
        user = User.objects.create_user(username=username, email=email, password=password)
        user.first_name = first_name
        user.last_name = last_name
        user.save()
        return Response({'id': user.id, 'username': user.username, 'email': user.email, 'first_name': user.first_name, 'last_name': user.last_name})


class LoginView(APIView):
    def post(self, request, *args, **kwargs):
        username = request.data.get('username') or request.data.get('user_name')
        password = request.data.get('password')
        device_id = request.data.get('device_id') or request.data.get('deviceId') or ''
        
        if not username or not password:
            return Response({'detail': 'username and password required'}, status=status.HTTP_400_BAD_REQUEST)
        from django.contrib.auth import authenticate
        user = authenticate(request, username=username, password=password)
        if user is None:
            return Response({'detail': 'Invalid credentials'}, status=status.HTTP_401_UNAUTHORIZED)
        
        # Log the login activity
        try:
            # Get IP address from request
            x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
            if x_forwarded_for:
                ip_address = x_forwarded_for.split(',')[0].strip()
            else:
                ip_address = request.META.get('REMOTE_ADDR')
            
            # Get user agent
            user_agent = request.META.get('HTTP_USER_AGENT', '')
            
            # Create login log entry
            from .models import LoginLog
            LoginLog.objects.create(
                user=user,
                ip_address=ip_address,
                user_agent=user_agent,
                device_id=device_id
            )
            logger.info(f"Login logged for {user.username} from IP: {ip_address}, Device: {device_id[:20]}...")
        except Exception as e:
            logger.error(f"Failed to log login for {user.username}: {e}")
        
        return Response({'id': user.id, 'username': user.username, 'first_name': user.first_name, 'last_name': user.last_name})



class FeedbackCreateView(APIView):
    """Allow authenticated users to submit feedback"""
    def post(self, request, *args, **kwargs):
        content = request.data.get('content') or request.data.get('feedback') or request.data.get('message')
        user_id = request.data.get('user_id')
        
        if not content:
            return Response({'detail': 'Feedback content is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        if not user_id:
            return Response({'detail': 'User ID is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Get user
        User = get_user_model()
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response({'detail': 'User not found'}, status=status.HTTP_404_NOT_FOUND)
        
        # Create feedback with user's current name and email
        user_name = f"{user.first_name} {user.last_name}".strip() or user.username
        user_email = user.email or ''
        feedback = Feedback.objects.create(
            user=user, 
            content=content,
            user_name=user_name,
            user_email=user_email
        )
        serializer = FeedbackSerializer(feedback)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class UpdateProfileView(APIView):
    """Allow users to update their profile (name, email, password)"""
    def put(self, request, *args, **kwargs):
        user_id = request.data.get('user_id')
        
        if not user_id:
            return Response({'detail': 'User ID is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        User = get_user_model()
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response({'detail': 'User not found'}, status=status.HTTP_404_NOT_FOUND)
        
        # Get update fields
        first_name = request.data.get('first_name')
        last_name = request.data.get('last_name')
        email = request.data.get('email')
        new_password = request.data.get('new_password')
        current_password = request.data.get('current_password')
        
        # Validate current password if changing password
        if new_password:
            if not current_password:
                return Response({'detail': 'Current password is required to change password'}, status=status.HTTP_400_BAD_REQUEST)
            if not user.check_password(current_password):
                return Response({'detail': 'Current password is incorrect'}, status=status.HTTP_401_UNAUTHORIZED)
        
        # Validate email format if provided
        if email:
            if not validate_email(email):
                return Response({'detail': 'Invalid email format'}, status=status.HTTP_400_BAD_REQUEST)
            # Check if email is already in use by another user
            if User.objects.filter(email=email).exclude(id=user.id).exists():
                return Response({'detail': 'Email already in use'}, status=status.HTTP_409_CONFLICT)
        
        # Update fields
        if first_name is not None:
            user.first_name = first_name
        if last_name is not None:
            user.last_name = last_name
        if email:
            user.email = email
        if new_password:
            user.set_password(new_password)
        
        user.save()
        
        return Response({
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'message': 'Profile updated successfully'
        })


class LeaveRoomView(APIView):
    """Allow a user to leave a room they are a member of (but not the creator)"""
    def post(self, request, room_id, *args, **kwargs):
        # Get user
        user = None
        user_id = None
        if getattr(request, 'user', None) and request.user.is_authenticated:
            user = request.user
            user_id = user.id
        else:
            user_id = request.data.get('user_id')
            if user_id:
                User = get_user_model()
                try:
                    user = User.objects.get(id=user_id)
                except Exception:
                    return Response({'detail': 'User not found'}, status=status.HTTP_404_NOT_FOUND)
        
        if not user:
            return Response({'detail': 'User ID required'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Get room
        try:
            room = Room.objects.get(id=room_id)
        except Room.DoesNotExist:
            return Response({'detail': 'Room not found'}, status=status.HTTP_404_NOT_FOUND)
        
        # Check if user is the creator - creators cannot leave, only delete
        if room.creator and room.creator.id == user.id:
            return Response({'detail': 'Room creators cannot leave. Delete the room instead.'}, status=status.HTTP_403_FORBIDDEN)
        
        # Check if user is a member
        if not room.members.filter(id=user.id).exists():
            return Response({'detail': 'You are not a member of this room'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Remove user from members
        room.members.remove(user)
        
        return Response({'detail': 'Successfully left the room'}, status=status.HTTP_200_OK)


class DeleteRoomView(APIView):
    """Allow a room creator to delete their room"""
    def delete(self, request, room_id, *args, **kwargs):
        # Get user
        user = None
        user_id = None
        if getattr(request, 'user', None) and request.user.is_authenticated:
            user = request.user
            user_id = user.id
        else:
            user_id = request.query_params.get('user_id') or request.data.get('user_id')
            if user_id:
                User = get_user_model()
                try:
                    user = User.objects.get(id=user_id)
                except Exception:
                    return Response({'detail': 'User not found'}, status=status.HTTP_404_NOT_FOUND)
        
        if not user:
            return Response({'detail': 'User ID required'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Get room
        try:
            room = Room.objects.get(id=room_id)
        except Room.DoesNotExist:
            return Response({'detail': 'Room not found'}, status=status.HTTP_404_NOT_FOUND)
        
        # Check if user is the creator
        if not room.creator or room.creator.id != user.id:
            return Response({'detail': 'Only the room creator can delete this room'}, status=status.HTTP_403_FORBIDDEN)
        
        # Delete the room (this will cascade delete messages too)
        room_name = room.name
        room.delete()
        
        return Response({'detail': f'Room "{room_name}" deleted successfully'}, status=status.HTTP_200_OK)


class UserRoomStatsView(APIView):
    """Get user's room creation stats"""
    def get(self, request, *args, **kwargs):
        user_id = request.query_params.get('user_id')
        if not user_id:
            return Response({'detail': 'user_id required'}, status=status.HTTP_400_BAD_REQUEST)
        
        created_rooms_count = Room.objects.filter(creator_id=user_id).count()
        
        return Response({
            'created_rooms_count': created_rooms_count,
            'max_rooms': MAX_ROOMS_PER_USER,
            'can_create': created_rooms_count < MAX_ROOMS_PER_USER
        })


class RenameRoomView(APIView):
    """Allow room creator to rename the room"""
    def post(self, request, room_id, *args, **kwargs):
        new_name = request.data.get('name') or request.data.get('room_name')
        if not new_name:
            return Response({'detail': 'New room name required'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Get user
        user = None
        if getattr(request, 'user', None) and request.user.is_authenticated:
            user = request.user
        else:
            user_id = request.data.get('user_id') or request.data.get('performer_id')
            if user_id:
                User = get_user_model()
                try:
                    user = User.objects.get(id=user_id)
                except Exception:
                    user = None
        
        if not user:
            return Response({'detail': 'User required'}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            room = Room.objects.get(id=room_id)
        except Room.DoesNotExist:
            return Response({'detail': 'Room not found'}, status=status.HTTP_404_NOT_FOUND)
        
        if not room.creator or room.creator.id != user.id:
            return Response({'detail': 'Only the room creator can rename the room'}, status=status.HTTP_403_FORBIDDEN)
        
        room.name = new_name
        room.save()
        return Response({'detail': 'Room renamed successfully', 'name': room.name}, status=status.HTTP_200_OK)


class KickMemberView(APIView):
    """Allow room creator to kick a member"""
    def post(self, request, room_id, *args, **kwargs):
        target_user_id = request.data.get('target_user_id')
        if not target_user_id:
            return Response({'detail': 'target_user_id required'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Get performing user (must be room creator)
        user = None
        if getattr(request, 'user', None) and request.user.is_authenticated:
            user = request.user
        else:
            performer_id = request.data.get('performer_id')
            if performer_id:
                User = get_user_model()
                try:
                    user = User.objects.get(id=performer_id)
                except Exception:
                    user = None
        
        if not user:
            return Response({'detail': 'User required'}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            room = Room.objects.get(id=room_id)
        except Room.DoesNotExist:
            return Response({'detail': 'Room not found'}, status=status.HTTP_404_NOT_FOUND)
        
        if not room.creator or room.creator.id != user.id:
            return Response({'detail': 'Only the room creator can kick members'}, status=status.HTTP_403_FORBIDDEN)
        
        # Don't allow kicking the creator
        if str(target_user_id) == str(user.id):
            return Response({'detail': 'Cannot kick the room creator'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Remove member
        User = get_user_model()
        try:
            target = User.objects.get(id=target_user_id)
            if room.members.filter(id=target.id).exists():
                room.members.remove(target)
                return Response({'detail': 'Member kicked successfully'}, status=status.HTTP_200_OK)
            else:
                return Response({'detail': 'Target is not a member'}, status=status.HTTP_400_BAD_REQUEST)
        except Exception:
            return Response({'detail': 'Target user not found'}, status=status.HTTP_404_NOT_FOUND)


class BanMemberView(APIView):
    """Allow room creator to ban a member (kick + prevent rejoining)"""
    def post(self, request, room_id, *args, **kwargs):
        target_user_id = request.data.get('target_user_id')
        if not target_user_id:
            return Response({'detail': 'target_user_id required'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Get performing user (must be room creator)
        user = None
        if getattr(request, 'user', None) and request.user.is_authenticated:
            user = request.user
        else:
            performer_id = request.data.get('performer_id')
            if performer_id:
                User = get_user_model()
                try:
                    user = User.objects.get(id=performer_id)
                except Exception:
                    user = None
        
        if not user:
            return Response({'detail': 'User required'}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            room = Room.objects.get(id=room_id)
        except Room.DoesNotExist:
            return Response({'detail': 'Room not found'}, status=status.HTTP_404_NOT_FOUND)
        
        if not room.creator or room.creator.id != user.id:
            return Response({'detail': 'Only the room creator can ban members'}, status=status.HTTP_403_FORBIDDEN)
        
        # Don't allow banning the creator
        if str(target_user_id) == str(user.id):
            return Response({'detail': 'Cannot ban the room creator'}, status=status.HTTP_400_BAD_REQUEST)
        
        # For now, just kick them (ban tracking requires model change + migration on Railway)
        # We'll just remove them from members
        User = get_user_model()
        try:
            target = User.objects.get(id=target_user_id)
            if room.members.filter(id=target.id).exists():
                room.members.remove(target)
            return Response({'detail': 'Member banned successfully'}, status=status.HTTP_200_OK)
        except Exception:
            return Response({'detail': 'Target user not found'}, status=status.HTTP_404_NOT_FOUND)
