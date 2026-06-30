from django.shortcuts import render
from django.db.models import Q
from django.views.generic import TemplateView
from django.shortcuts import get_object_or_404
from rest_framework import generics
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import (
    ChatSerializer,
    FriendSerializer,
    FriendRequestSerializer,
    MessageSerializer,
    AttachmentSerializer,
)
from .models import Chats, ChatMembers, Friends, FriendRequests, Messages, Attachments


# API that serves a list of all of the current users chats
class ChatAPIView(generics.ListAPIView):
    serializer_class = ChatSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Chats.objects.filter(chatmembers__user=self.request.user).distinct()


# API that serves a list of all of the current users friends
class FriendAPIView(generics.ListAPIView):
    serializer_class = FriendSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):

        # Get all friends where user is either the initiator or recipient of the friendship
        return Friends.objects.filter(
            Q(user=self.request.user) | Q(friend=self.request.user)
        )


# API that serves a list of all of the current users friend requests
class FriendRequestAPIView(generics.ListAPIView):
    serializer_class = FriendRequestSerializer
    permission_classes = [IsAuthenticated]

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
        message = get_object_or_404(Messages, pk=self.kwargs["message_id"])
        return Attachments.objects.filter(message=message)


# API that returns the current users id and username
class CurrentUserAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(
            {
                "id": request.user.id,
                "username": request.user.username,
            }
        )


# View that displays the main chat page
class ChatView(TemplateView):
    template_name = "chats.html"
    permission_classes = [IsAuthenticated]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["user"] = self.request.user
        context["is_authenticated"] = self.request.user.is_authenticated

        return context


# View that displays the main chat page
class FriendView(TemplateView):
    template_name = "friends.html"
    permission_classes = [IsAuthenticated]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["user"] = self.request.user
        context["is_authenticated"] = self.request.user.is_authenticated

        return context
