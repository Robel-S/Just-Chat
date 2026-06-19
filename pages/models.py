from django.db import models
from django.conf import settings


class Friends(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="friends"
    )
    friend = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="friends_of"
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user_id", "friend_id"], name="unique_friendship"
            )
        ]


class FriendRequests(models.Model):
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="sent_request"
    )
    receiver = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="recieved_request",
    )
    status = models.CharField(max_length=15, db_default="Pending")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(status__in=["Pending", "Accepted", "Rejected"]),
                name="valid_status_constraint",
            )
        ]


class Chats(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    name = models.CharField(max_length=50)
    chat_type = models.CharField(max_length=15)
    image = models.ImageField(upload_to="chats", default="default.png")

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(chat_type__in=["DM", "Groupchat"]),
                name="valid_chat_type_constraint",
            )
        ]


class ChatMembers(models.Model):
    chat = models.ForeignKey(Chats, on_delete=models.CASCADE)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["chat_id", "user_id"], name="unique_member")
        ]


class Messages(models.Model):
    chat = models.ForeignKey(Chats, on_delete=models.CASCADE)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    text = models.TextField(max_length=1000)
    timestamp = models.DateTimeField(auto_now_add=True)


class Attachments(models.Model):
    message = models.ForeignKey(Messages, on_delete=models.CASCADE)
    filename = models.CharField(max_length=200)
    filesize = models.BigIntegerField()
    data = models.FileField(upload_to="attachments")
