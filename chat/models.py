from django.db import models
from django.conf import settings
from django.utils.crypto import get_random_string


class Room(models.Model):
    name = models.CharField(max_length=200)
    key = models.CharField(max_length=16, unique=True, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    creator = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='created_rooms')
    members = models.ManyToManyField(settings.AUTH_USER_MODEL, related_name='rooms', blank=True)

    def save(self, *args, **kwargs):
        if not self.key:
            self.key = get_random_string(8).upper()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Message(models.Model):
    room = models.ForeignKey(Room, related_name='messages', on_delete=models.CASCADE)
    # keep user_name for backwards compatibility and display
    user_name = models.CharField(max_length=150)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user_name}: {self.content[:30]}"
