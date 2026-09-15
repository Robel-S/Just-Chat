import asyncio
import json

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from channels.testing import WebsocketCommunicator
from django.contrib.auth import get_user_model
from django.db import transaction
from django.test import TransactionTestCase
from django.urls import reverse
from rest_framework.test import APIClient

from .consumers import ChatConsumer, NotificationConsumer
from .message_composition import NotAChatMember, create_message_composition
from .models import ChatMembers, Chats

User = get_user_model()


async def receive_channel_event(channel_layer, channel_name):
    return await asyncio.wait_for(channel_layer.receive(channel_name), timeout=0.2)


class CreateMessageCompositionTests(TransactionTestCase):
    def setUp(self):
        self.author = User.objects.create_user(username="author", password="pw")
        self.recipient = User.objects.create_user(username="recipient", password="pw")
        self.outsider = User.objects.create_user(username="outsider", password="pw")
        self.chat = Chats.objects.create(
            owner=self.author,
            name="Composition",
            chat_type="DM",
        )
        ChatMembers.objects.create(chat=self.chat, user=self.author)
        ChatMembers.objects.create(chat=self.chat, user=self.recipient)

    def test_member_creates_one_message_with_the_canonical_projection(self):
        attachments = [
            {
                "name": "notes.txt",
                "size": 12,
                "url": "/media/attachments/notes.txt",
            }
        ]

        projection = create_message_composition(
            chat_id=self.chat.id,
            author=self.author,
            text="Hello",
            attachments=attachments,
        )

        client = APIClient()
        client.force_authenticate(user=self.author)
        response = client.get(reverse("messages_api", kwargs={"chat_id": self.chat.id}))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, [projection])
        self.assertEqual(projection["attachments"], attachments)

    def test_non_member_cannot_create_a_message(self):
        with self.assertRaises(NotAChatMember):
            create_message_composition(
                chat_id=self.chat.id,
                author=self.outsider,
                text="Private",
                attachments=[],
            )

        client = APIClient()
        client.force_authenticate(user=self.author)
        response = client.get(reverse("messages_api", kwargs={"chat_id": self.chat.id}))
        self.assertEqual(response.data, [])

    def test_creation_publishes_the_canonical_message_event(self):
        channel_layer = get_channel_layer()
        channel_name = async_to_sync(channel_layer.new_channel)("composition-test.")
        async_to_sync(channel_layer.group_add)(
            f"Chat_{self.chat.id}",
            channel_name,
        )

        projection = create_message_composition(
            chat_id=self.chat.id,
            author=self.author,
            text="Published",
            attachments=[],
        )

        event = async_to_sync(receive_channel_event)(channel_layer, channel_name)
        self.assertEqual(event, {"type": "chat_message", "message": projection})

    def test_recipient_unread_notification_is_published_only_after_commit(self):
        channel_layer = get_channel_layer()
        channel_name = async_to_sync(channel_layer.new_channel)("unread-test.")
        async_to_sync(channel_layer.group_add)(
            f"Notifications_{self.recipient.id}",
            channel_name,
        )

        with transaction.atomic():
            create_message_composition(
                chat_id=self.chat.id,
                author=self.author,
                text="Unread",
                attachments=[],
            )
            with self.assertRaises(TimeoutError):
                async_to_sync(receive_channel_event)(channel_layer, channel_name)

        event = async_to_sync(receive_channel_event)(channel_layer, channel_name)
        self.assertEqual(
            event,
            {
                "type": "unread_update",
                "chat_id": self.chat.id,
                "unread_count": 1,
            },
        )
        self.assertEqual(
            list(
                ChatMembers.objects.filter(chat=self.chat)
                .order_by("user_id")
                .values_list("user_id", "unread_count")
            ),
            [(self.author.id, 0), (self.recipient.id, 1)],
        )

    def test_rolled_back_creation_publishes_no_live_event(self):
        channel_layer = get_channel_layer()
        channel_name = async_to_sync(channel_layer.new_channel)("rollback-test.")
        async_to_sync(channel_layer.group_add)(
            f"Chat_{self.chat.id}",
            channel_name,
        )

        with self.assertRaises(RuntimeError):
            with transaction.atomic():
                create_message_composition(
                    chat_id=self.chat.id,
                    author=self.author,
                    text="Rollback",
                    attachments=[],
                )
                raise RuntimeError("roll back the accepted composition")

        with self.assertRaises(TimeoutError):
            async_to_sync(receive_channel_event)(channel_layer, channel_name)

        client = APIClient()
        client.force_authenticate(user=self.author)
        response = client.get(reverse("messages_api", kwargs={"chat_id": self.chat.id}))
        self.assertEqual(response.data, [])


class ChatConsumerAdapterTests(TransactionTestCase):
    async def test_current_websocket_send_uses_message_composition_behavior(self):
        author = await User.objects.acreate_user(username="ws-author", password="pw")
        recipient = await User.objects.acreate_user(
            username="ws-recipient", password="pw"
        )
        chat = await Chats.objects.acreate(
            owner=author,
            name="WebSocket adapter",
            chat_type="DM",
        )
        await ChatMembers.objects.acreate(chat=chat, user=author)
        await ChatMembers.objects.acreate(chat=chat, user=recipient)

        chat_communicator = WebsocketCommunicator(
            ChatConsumer.as_asgi(),
            f"/ws/chat/{chat.id}/",
        )
        chat_communicator.scope["user"] = author
        chat_communicator.scope["url_route"] = {"kwargs": {"chat_id": chat.id}}
        notification_communicator = WebsocketCommunicator(
            NotificationConsumer.as_asgi(),
            "/ws/notifications/",
        )
        notification_communicator.scope["user"] = recipient

        self.assertTrue((await chat_communicator.connect())[0])
        self.assertTrue((await notification_communicator.connect())[0])

        await chat_communicator.send_to(
            text_data=json.dumps(
                {
                    "text": "Through the interface",
                    "attachments": [{"name": "legacy.txt", "url": "/legacy.txt"}],
                }
            )
        )

        message = json.loads(await chat_communicator.receive_from(timeout=0.5))
        notification = json.loads(
            await notification_communicator.receive_from(timeout=0.5)
        )
        self.assertEqual(message["text"], "Through the interface")
        self.assertEqual(message["chat"], chat.id)
        self.assertEqual(message["user"], author.id)
        self.assertEqual(notification["unread_count"], 1)

        await chat_communicator.disconnect()
        await notification_communicator.disconnect()

    async def test_connected_user_cannot_send_after_membership_is_removed(self):
        author = await User.objects.acreate_user(
            username="removed-author", password="pw"
        )
        chat = await Chats.objects.acreate(
            owner=author,
            name="Membership changed",
            chat_type="DM",
        )
        membership = await ChatMembers.objects.acreate(chat=chat, user=author)
        communicator = WebsocketCommunicator(
            ChatConsumer.as_asgi(),
            f"/ws/chat/{chat.id}/",
        )
        communicator.scope["user"] = author
        communicator.scope["url_route"] = {"kwargs": {"chat_id": chat.id}}

        self.assertTrue((await communicator.connect())[0])
        await membership.adelete()
        await communicator.send_to(
            text_data=json.dumps({"text": "No longer allowed", "attachments": []})
        )

        self.assertEqual(
            await communicator.receive_output(timeout=0.5),
            {"type": "websocket.close", "code": 4403},
        )
