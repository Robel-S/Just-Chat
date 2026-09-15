from pages.serializers import ChatMembersSerializer
from django.shortcuts import render
from django.db import transaction
from django.db.models import Q
from django.views.generic import TemplateView
from django.shortcuts import get_object_or_404
from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin
from rest_framework import generics
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import status

from .serializers import (
    ChatSerializer,
    ChatMembersSerializer,
    FriendSerializer,
    FriendRequestSerializer,
    MessageSerializer,
    AttachmentSerializer,
    UserSerializer,
    CreateFriendRequestSerializer,
)
from .models import Chats, ChatMembers, Friends, FriendRequests, Messages, Attachments


# API that serves a list of all of the current users chats
class ChatAPIView(generics.ListAPIView):
    serializer_class = ChatSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Chats.objects.filter(chatmembers__user=self.request.user).distinct()


class CreateChatAPIView(generics.CreateAPIView):
    serializer_class = ChatSerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        chat = serializer.save(owner=self.request.user)
        ChatMembers.objects.create(chat=chat, user=self.request.user)


class handleChatAPIView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = ChatSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = "id"
    lookup_url_kwarg = "chat_id"

    def get_queryset(self):
        queryset = Chats.objects.filter(chatmembers__user=self.request.user)
        if self.request.method in {"PUT", "PATCH", "DELETE"}:
            queryset = queryset.filter(owner=self.request.user)
        return queryset.distinct()


class ChatMembersAPIView(generics.ListAPIView):
    serializer_class = ChatMembersSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return ChatMembers.objects.filter(
            chat=self.kwargs["chat_id"],
            chat__chatmembers__user=self.request.user,
        ).distinct()


class MarkChatReadAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, chat_id):
        membership = get_object_or_404(
            ChatMembers,
            chat_id=chat_id,
            user=request.user,
        )

        if membership.unread_count:
            membership.unread_count = 0
            membership.save(update_fields=["unread_count"])

        return Response({"chat_id": chat_id, "unread_count": 0})


class handleChatMembersAPIView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = ChatMembersSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = "user_id"
    lookup_url_kwarg = "user_id"

    def get_queryset(self):
        return ChatMembers.objects.filter(
            user=self.kwargs["user_id"],
            chat=self.kwargs["chat_id"],
        ).filter(Q(chat__owner=self.request.user) | Q(user=self.request.user))

    @transaction.atomic
    def delete(self, request, *args, **kwargs):
        instance = self.get_object()
        chat = instance.chat
        leaving_user = instance.user

        # Delete the member
        instance.delete()

        # Check remaining members
        remaining_memberships = ChatMembers.objects.filter(chat=chat)
        remaining_count = remaining_memberships.count()

        chat_deleted = False
        new_owner_id = None

        if remaining_count <= 1:
            chat.delete()
            chat_deleted = True
        else:
            # Reassign ownership if the leaving user was the owner
            if getattr(chat, "owner_id", None) == leaving_user.id:
                next_member = remaining_memberships.first()
                chat.owner = next_member.user
                chat.save(update_fields=["owner"])
                new_owner_id = next_member.user.id

        return Response(
            {
                "detail": "Member removed successfully.",
                "chat_deleted": chat_deleted,
                "new_owner_id": new_owner_id,
                "remaining_members_count": remaining_count if not chat_deleted else 0,
            },
            status=status.HTTP_200_OK,
        )


class CreateChatMembersAPIView(APIView):
    serializer_class = ChatMembersSerializer
    permission_classes = [IsAuthenticated]

    def post(self, request, chat_id):
        chat = get_object_or_404(Chats, pk=chat_id, owner=request.user)

        data = [{"user": member_id} for member_id in request.data.get("members", [])]

        serializer = self.serializer_class(data=data, many=True)
        serializer.is_valid(raise_exception=True)

        # Pass the chat instance to save()
        serializer.save(chat=chat)

        return Response({"status": "success", "data": serializer.data})


# API that serves a list of all of the current users friends
class FriendAPIView(generics.ListAPIView):
    serializer_class = FriendSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):

        # Get all friends where user is either the initiator or recipient of the friendship
        return Friends.objects.filter(
            Q(user=self.request.user) | Q(friend=self.request.user)
        )


class CreateFriendAPIView(generics.CreateAPIView):
    serializer_class = FriendSerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


# API that serves a list of all of the current users friend requests
class FriendRequestAPIView(generics.ListAPIView):
    serializer_class = FriendRequestSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return FriendRequests.objects.filter(receiver=self.request.user)


class CreateFriendRequestAPIView(generics.CreateAPIView):
    serializer_class = CreateFriendRequestSerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(sender=self.request.user, status="Pending")


class UpdateFriendRequestAPIView(generics.UpdateAPIView):
    serializer_class = FriendRequestSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = "sender__id"
    lookup_url_kwarg = "sender_id"

    def get_queryset(self):
        return FriendRequests.objects.filter(receiver=self.request.user)


# API that serves a list of all of the messages in a specified chat
class MessageAPIView(generics.ListAPIView):
    serializer_class = MessageSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        chat = get_object_or_404(
            Chats.objects.filter(chatmembers__user=self.request.user),
            pk=self.kwargs["chat_id"],
        )
        return Messages.objects.filter(chat=chat)


# API that serves all of the attachments tied to a specified message
class AttachmentAPIView(generics.ListAPIView):
    serializer_class = AttachmentSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        message = get_object_or_404(
            Messages.objects.filter(chat__chatmembers__user=self.request.user),
            pk=self.kwargs["message_id"],
        )
        return Attachments.objects.filter(message=message)


class CreateAttachmentsAPIView(APIView):
    serializer_class = AttachmentSerializer
    permission_classes = [IsAuthenticated]

    def post(self, request):
        files = request.FILES.getlist("file")

        if not files:
            return Response(
                {"error": "No files provided"}, status=status.HTTP_400_BAD_REQUEST
            )

        attachments = []

        for file in files:
            attachment = Attachments.objects.create(file=file)

            attachments.append(
                {
                    "id": attachment.id,
                    "file": attachment.file.url,
                    "name": attachment.file.name,
                    "type": file.content_type,
                    "size": file.size,
                }
            )

        return Response({"attachments": attachments}, status=status.HTTP_201_CREATED)


# API that returns the current users id and username
class CurrentUserAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(
            {
                "id": request.user.id,
                "username": request.user.username,
                "prof_pic": (
                    request.user.prof_pic.url if request.user.prof_pic else None
                ),
            }
        )


# API that allows searching for users by username
class UserSearchAPIView(generics.ListAPIView):
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        query = self.kwargs.get("q", "")

        exclude_ids = {self.request.user.id}

        related_user_ids = Friends.objects.filter(
            Q(user=self.request.user) | Q(friend=self.request.user)
        ).values_list("user", "friend")

        for u_id, f_id in related_user_ids:
            exclude_ids.add(u_id)
            exclude_ids.add(f_id)

        incoming_requests_ids = FriendRequests.objects.filter(
            Q(sender=self.request.user) | Q(receiver=self.request.user)
        ).values_list("sender", "receiver")

        for u_id, f_id in incoming_requests_ids:
            exclude_ids.add(u_id)
            exclude_ids.add(f_id)

        return (
            get_user_model()
            .objects.filter(username__icontains=query)
            .exclude(id__in=exclude_ids)
            .order_by("username")
            .distinct()
        )


class FriendSearchAPIView(generics.ListAPIView):
    serializer_class = FriendSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        query = self.kwargs.get("q", "")
        return Friends.objects.filter(
            Q(user=self.request.user, friend__username__icontains=query)
            | Q(friend=self.request.user, user__username__icontains=query)
        )


# View that displays the main chat page
class ChatView(LoginRequiredMixin, TemplateView):
    template_name = "chats.html"
    permission_classes = [IsAuthenticated]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["user"] = self.request.user
        context["is_authenticated"] = self.request.user.is_authenticated

        return context


# View that displays the main chat page
class FriendView(LoginRequiredMixin, TemplateView):
    template_name = "friends.html"
    permission_classes = [IsAuthenticated]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["user"] = self.request.user
        context["is_authenticated"] = self.request.user.is_authenticated

        return context
