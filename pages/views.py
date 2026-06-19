from django.shortcuts import render
from django.db.models import Q
from django.views.generic import TemplateView
from django.shortcuts import get_object_or_404
from rest_framework import generics
from rest_framework.permissions import IsAuthenticated

from .serializers import (
    ChatSerializer,
    FriendSerializer,
    FriendRequestSerializer,
    MessageSerializer,
    AttachmentSerializer,
)
from .models import Chats, ChatMembers, Friends, FriendRequests, Messages, Attachments


class ChatAPIView(generics.ListAPIView):
    serializer_class = ChatSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Chats.objects.filter(chatmembers__user=self.request.user).distinct()


class FriendAPIView(generics.ListAPIView):
    serializer_class = FriendSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Friends.objects.filter(
            Q(user=self.request.user) | Q(friend=self.request.user)
        )


class FriendRequestAPIView(generics.ListAPIView):
    serializer_class = FriendRequestSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return FriendRequests.objects.filter(receiver=self.request.user)


class MessageAPIView(generics.ListAPIView):
    serializer_class = MessageSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        chat = get_object_or_404(
            Chats.objects.filter(chatmembers__user=self.request.user),
            pk=self.kwargs["chat_id"],
        )
        return Messages.objects.filter(chat=chat)


class CreateMessageAPIView(generics.CreateAPIView):
    serializer_class = MessageSerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        chat_id = self.kwargs["chat_id"]
        membership = get_object_or_404(
            ChatMembers, chat_id=chat_id, user=self.request.user
        )
        serializer.save(chat=membership.chat, user=self.request.user)


class AttachmentAPIView(generics.ListAPIView):
    serializer_class = AttachmentSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        message = get_object_or_404(Messages, pk=self.kwargs["message_id"])
        return Attachments.objects.filter(message=message)


class ChatView(TemplateView):
    template_name = "chats.html"
    permission_classes = [IsAuthenticated]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["user"] = self.request.user
        context["is_authenticated"] = self.request.user.is_authenticated

        return context
