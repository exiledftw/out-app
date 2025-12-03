from django.test import TestCase
from .models import Room, Message


class ChatModelTests(TestCase):
    def test_create_room_and_message(self):
        room = Room.objects.create(name='Test Room')
        message = Message.objects.create(room=room, user_name='tester', content='Hello')
        self.assertEqual(Message.objects.count(), 1)
        self.assertEqual(room.messages.count(), 1)
