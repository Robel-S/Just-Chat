from rest_framework import serializers
from .models import Chats, Friends, FriendRequests, Messages, Attachments


class ChatSerializer(serializers.ModelSerializer):
    class Meta:
        model = Chats
        fields = ("id", "owner", "name", "chat_type", "image")


class FriendSerializer(serializers.ModelSerializer):
    user_username = serializers.CharField(source="user.username", read_only=True)
    friend_username = serializers.CharField(source="friend.username", read_only=True)

    class Meta:
        model = Friends
        fields = ("id", "user", "friend", "user_username", "friend_username")


class FriendRequestSerializer(serializers.ModelSerializer):
    sender_username = serializers.CharField(source="sender.username", read_only=True)
    receiver_username = serializers.CharField(
        source="receiver.username", read_only=True
    )

    class Meta:
        model = FriendRequests
        fields = (
            "id",
            "sender",
            "receiver",
            "sender_username",
            "receiver_username",
            "status",
            "created_at",
        )


class MessageSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username", read_only=True)

    class Meta:
        model = Messages
        fields = ("id", "chat", "user", "username", "text", "timestamp")
        read_only_fields = ("id", "chat", "user", "timestamp")


class AttachmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Attachments
        fields = ("id", "message", "filename", "filesize", "data")
