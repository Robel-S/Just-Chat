import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async

from .message_composition import NotAChatMember, create_message_composition
from .models import ChatMembers


class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        """Accept authenticated Chat Members into the Chat's live group."""
        self.chat_id = self.scope["url_route"]["kwargs"]["chat_id"]
        self.room_group_name = f"Chat_{self.chat_id}"

        user = self.scope["user"]
        if user.is_anonymous:
            await self.close(code=4401)
            return

        if not await self.is_chat_member(self.chat_id, user.id):
            await self.close(code=4403)
            return

        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name,
        )

        await self.accept()

    async def disconnect(self, close_code):
        """Remove the socket from its Chat group when it disconnects."""
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name,
        )

    async def receive(self, text_data):
        """Validate a WebSocket submission and create its Message Composition."""
        try:
            data = json.loads(text_data)
            text = data["text"]
            attachments = data.get("attachments", [])
        except (json.JSONDecodeError, KeyError):
            await self.close(code=400)
            return

        if not isinstance(text, str) or not isinstance(attachments, list):
            await self.close(code=400)
            return

        user = self.scope["user"]

        try:
            await database_sync_to_async(create_message_composition)(
                chat_id=self.chat_id,
                author=user,
                text=text,
                attachments=attachments,
            )
        except NotAChatMember:
            await self.close(code=4403)

    async def chat_message(self, event):
        """Forward a canonical Message projection to this browser."""
        await self.send(text_data=json.dumps(event["message"]))

    @database_sync_to_async
    def is_chat_member(self, chat_id, user_id):
        """Return whether a user currently belongs to a Chat."""
        return ChatMembers.objects.filter(chat_id=chat_id, user_id=user_id).exists()


class NotificationConsumer(AsyncWebsocketConsumer):

    async def connect(self):
        """Subscribe an authenticated user to their unread notification group."""
        user = self.scope["user"]

        # Don't allow anonymous users to connect
        if user.is_anonymous:
            await self.close()
            return

        self.user = user

        # Every user gets their own notification group
        self.notification_group_name = f"Notifications_{user.id}"

        await self.channel_layer.group_add(
            self.notification_group_name,
            self.channel_name,
        )

        await self.accept()

    async def disconnect(self, close_code):
        """Remove the socket from its notification group when connected."""
        if hasattr(self, "notification_group_name"):
            await self.channel_layer.group_discard(
                self.notification_group_name,
                self.channel_name,
            )

    async def unread_update(self, event):
        """Forward an unread-count update to the subscribed browser."""
        await self.send(
            text_data=json.dumps(
                {
                    "type": "unread_update",
                    "chat_id": event["chat_id"],
                    "unread_count": event["unread_count"],
                }
            )
        )
