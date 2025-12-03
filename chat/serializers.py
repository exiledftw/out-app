from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import Room, Message

User = get_user_model()


class MessageSerializer(serializers.ModelSerializer):
    user_id = serializers.IntegerField(source='user.id', read_only=True)
    class Meta:
        model = Message
        fields = ('id', 'user_name', 'user_id', 'content', 'created_at')


class RoomSerializer(serializers.ModelSerializer):
    last_messages = serializers.SerializerMethodField()
    creator_id = serializers.IntegerField(source='creator.id', read_only=True)
    members = serializers.SerializerMethodField()

    class Meta:
        model = Room
        fields = ('id', 'name', 'created_at', 'key', 'creator_id', 'members', 'last_messages')

    def get_last_messages(self, obj):
        msgs = obj.messages.order_by('-created_at')[:10]
        return MessageSerializer(msgs, many=True).data

    def get_members(self, obj):
        return [{'id': u.id, 'username': u.username, 'first_name': getattr(u, 'first_name', ''), 'last_name': getattr(u, 'last_name', '')} for u in obj.members.all()]
