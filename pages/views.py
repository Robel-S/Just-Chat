from django.shortcuts import render
from django.db.models import Q
from rest_framework import generics

from .serializers import ChatSerializer, FriendSerializer, FriendRequestSerializer
from .models import Chats, Friends, FriendRequests

class ChatAPIView(generics.ListAPIView):
    serializer_class = ChatSerializer

    def get_queryset(self):
        return Chats.objects.filter(
            chatmembers__user=self.request.user).distinct()

class FriendAPIView(generics.ListAPIView):
    serializer_class = FriendSerializer

    def get_queryset(self):
        return Friends.objects.filter(Q(user=self.request.user) | Q(friend=self.request.user))
           
class FriendRequestAPIView(generics.ListAPIView):
    serializer_class = FriendRequestSerializer

    def get_queryset(self):
        return FriendRequests.objects.filter(receiver=self.request.user)