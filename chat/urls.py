from django.urls import path
from .views import RoomListCreateView, RoomRetrieveView, MessageListCreateView, JoinRoomView
from .views import RegisterView, LoginView, LeaveRoomView, DeleteRoomView, UserRoomStatsView
from .views import RenameRoomView, KickMemberView, BanMemberView

urlpatterns = [
    path('rooms/', RoomListCreateView.as_view(), name='rooms-list'),
    path('rooms/join/', JoinRoomView.as_view(), name='rooms-join'),
    path('rooms/stats/', UserRoomStatsView.as_view(), name='rooms-stats'),
    path('rooms/<int:room_id>/', RoomRetrieveView.as_view(), name='room-detail'),
    path('rooms/<int:room_id>/messages/', MessageListCreateView.as_view(), name='room-messages'),
    path('rooms/<int:room_id>/leave/', LeaveRoomView.as_view(), name='room-leave'),
    path('rooms/<int:room_id>/delete/', DeleteRoomView.as_view(), name='room-delete'),
    path('rooms/<int:room_id>/rename/', RenameRoomView.as_view(), name='room-rename'),
    path('rooms/<int:room_id>/kick/', KickMemberView.as_view(), name='room-kick'),
    path('rooms/<int:room_id>/ban/', BanMemberView.as_view(), name='room-ban'),
    path('auth/register/', RegisterView.as_view(), name='auth-register'),
    path('auth/login/', LoginView.as_view(), name='auth-login'),
]
