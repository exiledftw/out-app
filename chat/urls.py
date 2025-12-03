from django.urls import path
from .views import RoomListCreateView, RoomRetrieveView, MessageListCreateView, JoinRoomView
from .views import RegisterView, LoginView

urlpatterns = [
    path('rooms/', RoomListCreateView.as_view(), name='rooms-list'),
    path('rooms/join/', JoinRoomView.as_view(), name='rooms-join'),
    path('rooms/<int:room_id>/', RoomRetrieveView.as_view(), name='room-detail'),
    path('rooms/<int:room_id>/messages/', MessageListCreateView.as_view(), name='room-messages'),
    path('auth/register/', RegisterView.as_view(), name='auth-register'),
    path('auth/login/', LoginView.as_view(), name='auth-login'),
]
