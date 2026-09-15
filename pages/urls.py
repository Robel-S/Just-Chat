from django.urls import path

from .views import (
    ChatAPIView,
    FriendAPIView,
    FriendRequestAPIView,
    MessageAPIView,
    CurrentUserAPIView,
    ChatView,
    FriendView,
    AttachmentAPIView,
    UserSearchAPIView,
    FriendSearchAPIView,
    CreateFriendRequestAPIView,
    UpdateFriendRequestAPIView,
    CreateFriendAPIView,
    CreateChatAPIView,
    CreateChatMembersAPIView,
    handleChatAPIView,
    ChatMembersAPIView,
    MarkChatReadAPIView,
    handleChatMembersAPIView,
    CreateAttachmentsAPIView,
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
    path(
        "api/search_users/<str:q>", UserSearchAPIView.as_view(), name="search_users_api"
    ),
    path(
        "api/search_friends/<str:q>",
        FriendSearchAPIView.as_view(),
        name="search_friends_api",
    ),
    path(
        "api/friend_requests/create",
        CreateFriendRequestAPIView.as_view(),
        name="create_request_api",
    ),
    path(
        "api/friend_requests/<int:sender_id>/update",
        UpdateFriendRequestAPIView.as_view(),
        name="update_request_api",
    ),
    path("api/friend/create", CreateFriendAPIView.as_view(), name="create_friend_api"),
    path("api/chats/create", CreateChatAPIView.as_view(), name="create_chat_api"),
    path(
        "api/chats/<int:chat_id>/members",
        CreateChatMembersAPIView.as_view(),
        name="create_members_api",
    ),
    path(
        "api/chats/<int:chat_id>/read/",
        MarkChatReadAPIView.as_view(),
        name="mark_chat_read_api",
    ),
    path(
        "api/chats/<int:chat_id>/", handleChatAPIView.as_view(), name="handle_chat_api"
    ),
    path(
        "api/members/<int:chat_id>/",
        ChatMembersAPIView.as_view(),
        name="chat_members_api",
    ),
    path(
        "api/members/<int:chat_id>/<int:user_id>/edit/",
        handleChatMembersAPIView.as_view(),
        name="handle_chat_members_api",
    ),
    path(
        "api/attachments/create/",
        CreateAttachmentsAPIView.as_view(),
        name="create_attachments_api",
    ),
    path("chats", ChatView.as_view(), name="chats"),
    path("friends", FriendView.as_view(), name="friends"),
]
