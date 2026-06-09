from django.urls import path

from .views import ChatAPIView, FriendAPIView, FriendRequestAPIView
urlpatterns = [
    path("chats", ChatAPIView.as_view(), name="chats"),
    path("friends", FriendAPIView.as_view(), name="friends"),
    path("friend_requests", FriendRequestAPIView.as_view(), name="requests"),
]