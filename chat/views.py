from rest_framework import generics
from rest_framework.response import Response
from rest_framework import status
from .models import Room, Message
from .serializers import RoomSerializer, MessageSerializer
from rest_framework.views import APIView
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db import models as dj_models
from django.contrib.auth import get_user_model
from django.contrib.auth.models import User as DjangoUser
import random
import string


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

        # Broadcast
        try:
            channel_layer = get_channel_layer()
            async_to_sync(channel_layer.group_send)(
                f'room_{room_id}',
                {'type': 'chat.message', 'message': serializer.data},
            )
        except Exception:
            pass

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


class RegisterView(APIView):
    def post(self, request, *args, **kwargs):
        username = request.data.get('username') or request.data.get('user_name')
        password = request.data.get('password')
        first_name = request.data.get('first_name') or request.data.get('firstName') or ''
        last_name = request.data.get('last_name') or request.data.get('lastName') or ''
        if not (username and password):
            return Response({'detail': 'username and password required'}, status=status.HTTP_400_BAD_REQUEST)
        User = get_user_model()
        if User.objects.filter(username=username).exists():
            return Response({'detail': 'Username already taken'}, status=status.HTTP_409_CONFLICT)
        user = User.objects.create_user(username=username, email=f'{username}@example.local', password=password)
        user.first_name = first_name
        user.last_name = last_name
        user.save()
        return Response({'id': user.id, 'username': user.username, 'first_name': user.first_name, 'last_name': user.last_name})


class LoginView(APIView):
    def post(self, request, *args, **kwargs):
        username = request.data.get('username') or request.data.get('user_name')
        password = request.data.get('password')
        if not username or not password:
            return Response({'detail': 'username and password required'}, status=status.HTTP_400_BAD_REQUEST)
        from django.contrib.auth import authenticate
        user = authenticate(request, username=username, password=password)
        if user is None:
            return Response({'detail': 'Invalid credentials'}, status=status.HTTP_401_UNAUTHORIZED)
        return Response({'id': user.id, 'username': user.username, 'first_name': user.first_name, 'last_name': user.last_name})
