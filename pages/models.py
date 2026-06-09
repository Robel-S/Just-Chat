from django.db import models
from django.conf import settings

class Friends(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="friends")
    friend = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="friends_of")

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields = ['user_id', 'friend_id'],
                name='unique_friendship'
            )
        ]

class FriendRequests(models.Model):
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="sent_request")
    receiver = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="recieved_request")
    status = models.CharField(max_length=15, db_default = "Pending")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        models.CheckConstraint(
            condition=models.Q(status_in=["Pending", "Accepted", "Rejected"]),
            name='valid_status_constraint'
        )

class Chats(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    name = models.CharField(max_length=50)
    type = models.CharField(max_length=15)

    class Meta:
        models.CheckConstraint(
            condition=models.Q(type_in=["DM", "Groupchat"]),
            name='valid_chat_type_constraint'
        )

class ChatMembers(models.Model):
    chat = models.ForeignKey(Chats, on_delete = models.CASCADE)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields = ['chat_id', 'user_id'],
                name='unique_member'
            )
        ]