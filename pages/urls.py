from django.urls import path

from .views import (
    ChatAPIView,
    FriendAPIView,
    FriendRequestAPIView,
    MessageAPIView,
    CurrentUserAPIView,
    ChatView,
    AttachmentAPIView,
)

urlpatterns = [
    path("api/chats", ChatAPIView.as_view(), name="chats_api"),
    path("api/friends", FriendAPIView.as_view(), name="friends_api"),
    path("api/friend_requests", FriendRequestAPIView.as_view(), name="requests_api"),
    path("api/<int:chat_id>/messages/", MessageAPIView.as_view(), name="messages_api"),
    path(
        "api/<int:message_id>/attachments/",
        AttachmentAPIView.as_view(),
        name="attachments_api",
    ),
    path("api/me", CurrentUserAPIView.as_view(), name="me"),
    path("chats", ChatView.as_view(), name="chats"),
]
