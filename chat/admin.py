from django.contrib import admin
from .models import Room, Message, Feedback, LoginLog

@admin.register(Room)
class RoomAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'key', 'creator', 'created_at')
    filter_horizontal = ('members',)


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ('id', 'user_name', 'user', 'room', 'created_at')


@admin.register(Feedback)
class FeedbackAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'user_name', 'user_email', 'content', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('user__username', 'user_name', 'user_email', 'content')


@admin.register(LoginLog)
class LoginLogAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'ip_address', 'device_id', 'user_agent', 'logged_at')
    list_filter = ('logged_at', 'user')
    search_fields = ('user__username', 'ip_address', 'device_id')
    readonly_fields = ('user', 'ip_address', 'device_id', 'user_agent', 'logged_at')


