import logging
from functools import partial

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db import transaction

from .models import ChatMembers, Messages
from .serializers import MessageSerializer

logger = logging.getLogger(__name__)


class NotAChatMember(PermissionError):
    """Raised when an author cannot create a Message in a Chat."""


@transaction.atomic
def create_message_composition(*, chat_id, author, text, attachments):
    membership = (
        ChatMembers.objects.select_for_update()
        .select_related("chat")
        .filter(chat_id=chat_id, user=author)
        .first()
    )
    if membership is None:
        raise NotAChatMember

    message = Messages.objects.create(
        chat=membership.chat,
        user=author,
        text=text,
        attachments=attachments,
    )
    recipients = list(
        ChatMembers.objects.select_for_update()
        .filter(chat_id=chat_id)
        .exclude(user=author)
        .order_by("id")
    )
    for recipient in recipients:
        recipient.unread_count += 1
    ChatMembers.objects.bulk_update(recipients, ["unread_count"])

    projection = dict(MessageSerializer(message).data)
    unread_events = [
        {
            "user_id": recipient.user_id,
            "chat_id": chat_id,
            "unread_count": recipient.unread_count,
        }
        for recipient in recipients
    ]
    transaction.on_commit(partial(_publish_creation, projection, unread_events))
    return projection


def _publish_creation(projection, unread_events):
    channel_layer = get_channel_layer()
    events = [
        (
            f"Chat_{projection['chat']}",
            {"type": "chat_message", "message": projection},
        ),
        *[
            (
                f"Notifications_{event['user_id']}",
                {
                    "type": "unread_update",
                    "chat_id": event["chat_id"],
                    "unread_count": event["unread_count"],
                },
            )
            for event in unread_events
        ],
    ]

    for group_name, event in events:
        try:
            async_to_sync(channel_layer.group_send)(group_name, event)
        except Exception:
            logger.exception(
                "Message %s was committed but an event could not be published",
                projection["id"],
            )
