from django.db.models.signals import post_save
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from django.db.models import F
from django.dispatch import receiver

from .models import Messages, ChatMembers


@receiver(post_save, sender=Messages)
def notify_unread_count(sender, instance, created, **kwargs):
    if not created:
        return

    channel_layer = get_channel_layer()

    other_members = ChatMembers.objects.filter(chat=instance.chat).exclude(
        user=instance.user
    )

    other_members.update(unread_count=F("unread_count") + 1)

    # Notify each member with their updated count
    for member in other_members.select_related("user"):
        member.refresh_from_db()

        group_name = f"Notifications_{member.user_id}"
        async_to_sync(channel_layer.group_send)(
            group_name,
            {
                "type": "unread_update",
                "chat_id": instance.chat_id,
                "unread_count": member.unread_count,
            },
        )
