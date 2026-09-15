from rest_framework import serializers
from .models import Chats, ChatMembers, Friends, FriendRequests, Messages, Attachments
from django.contrib.auth import get_user_model


class ChatSerializer(serializers.ModelSerializer):
    unread_count = serializers.SerializerMethodField()

    class Meta:
        model = Chats
        fields = ("id", "owner", "name", "chat_type", "image", "unread_count")
        read_only_fields = ("id", "owner")

    def get_unread_count(self, obj):
        request = self.context.get("request")
        if not request or request.user.is_anonymous:
            return 0

        # Query the ChatMembers record specifically for the requesting user
        member = ChatMembers.objects.filter(chat=obj, user=request.user).first()
        return member.unread_count if member else 0


class ChatMembersSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username", read_only=True)
    prof_pic = serializers.CharField(source="user.prof_pic.url", read_only=True)

    class Meta:
        model = ChatMembers
        fields = ("id", "chat", "user", "username", "prof_pic")
        read_only_fields = ("id", "chat")


class FriendSerializer(serializers.ModelSerializer):
    user_username = serializers.CharField(source="user.username", read_only=True)
    friend_username = serializers.CharField(source="friend.username", read_only=True)

    class Meta:
        model = Friends
        fields = ("id", "user", "friend", "user_username", "friend_username")
        read_only_fields = ("id", "user")


class FriendRequestSerializer(serializers.ModelSerializer):
    sender_username = serializers.CharField(source="sender.username", read_only=True)
    receiver_username = serializers.CharField(
        source="receiver.username", read_only=True
    )
    partial = True  # Allow partial updates

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


class CreateFriendRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = FriendRequests
        fields = ("id", "sender", "receiver", "status", "created_at")
        read_only_fields = ("id", "sender", "status", "created_at")


class MessageSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username", read_only=True)
    prof_pic = serializers.CharField(source="user.prof_pic.url", read_only=True)

    class Meta:
        model = Messages
        fields = (
            "id",
            "chat",
            "user",
            "username",
            "prof_pic",
            "text",
            "timestamp",
            "attachments",
        )
        read_only_fields = ("id", "chat", "user", "timestamp")


class AttachmentSerializer(serializers.ModelSerializer):
    name = serializers.SerializerMethodField()
    size = serializers.SerializerMethodField()

    class Meta:
        model = Attachments
        fields = ("id", "message", "name", "size", "file")
        read_only_fields = ("id", "name", "size")

    def get_name(self, obj):
        return obj.file.name.rsplit("/", 1)[-1] if obj.file else ""

    def get_size(self, obj):
        return obj.file.size if obj.file else 0


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = get_user_model()
        fields = ("id", "username", "prof_pic")
