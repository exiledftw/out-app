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


class Feedback(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='feedbacks')
    user_name = models.CharField(max_length=150, blank=True)  # Name at time of feedback
    user_email = models.EmailField(blank=True)  # Email at time of feedback
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Feedback from {self.user.username}: {self.content[:50]}"


class LoginLog(models.Model):
    """Logs each user login with device/network info"""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='login_logs')
    ip_address = models.GenericIPAddressField(null=True, blank=True, db_column='IPaddr')
    user_agent = models.TextField(blank=True)
    device_id = models.CharField(max_length=255, blank=True, db_column='MAC')  # Device fingerprint
    logged_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-logged_at']
        verbose_name = 'Login Log'
        verbose_name_plural = 'Login Logs'

    def __str__(self):
        return f"{self.user.username} logged in at {self.logged_at} from {self.ip_address}"



