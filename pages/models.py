from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError


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
            ),
            models.UniqueConstraint(
                fields=["sender_id", "receiver_id"],
                name="unique_friend_request",
            ),
        ]

    def clean(self):
        if self.sender_id and self.receiver_id:
            if FriendRequests.objects.filter(
                sender=self.receiver,
                receiver=self.sender,
            ).exists():
                raise ValidationError(
                    "A friend request already exists in the opposite direction."
                )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


class Chats(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    name = models.CharField(max_length=50)
    chat_type = models.CharField(max_length=15)
    image = models.ImageField(upload_to="chats/", default="default.png")

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
    unread_count = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["chat_id", "user_id"], name="unique_member")
        ]


class Messages(models.Model):
    chat = models.ForeignKey(Chats, on_delete=models.CASCADE)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    text = models.TextField(max_length=1000)
    timestamp = models.DateTimeField(auto_now_add=True)
    attachments = models.JSONField(
        default=list,
        blank=True,
    )


class Attachments(models.Model):
    message = models.ForeignKey(
        Messages,
        null=True,
        blank=True,
        related_name="messages",
        on_delete=models.CASCADE,
    )
    file = models.FileField(upload_to="attachments")
