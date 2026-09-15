import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async

from .message_composition import NotAChatMember, create_message_composition
from .models import ChatMembers


class ChatConsumer(AsyncWebsocketConsumer):
    # gets chat id from url and adds user to appropriate group in channel then connects
    async def connect(self):
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

    # removes user from the group and disconnects from websocket server
    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name,
        )

    # when a messsage is recieved from the frontend saves the message in the database and sends it to the group
    async def receive(self, text_data):
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

    # runs for each user and the group and sends the message data back to the browser
    async def chat_message(self, event):
        await self.send(text_data=json.dumps(event["message"]))

    # saves message in the database
    @database_sync_to_async
    def is_chat_member(self, chat_id, user_id):
        return ChatMembers.objects.filter(chat_id=chat_id, user_id=user_id).exists()


class NotificationConsumer(AsyncWebsocketConsumer):

    async def connect(self):
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
        if hasattr(self, "notification_group_name"):
            await self.channel_layer.group_discard(
                self.notification_group_name,
                self.channel_name,
            )

    async def unread_update(self, event):
        await self.send(
            text_data=json.dumps(
                {
                    "type": "unread_update",
                    "chat_id": event["chat_id"],
                    "unread_count": event["unread_count"],
                }
            )
        )
