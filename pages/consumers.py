import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async

from .models import Chats, Messages, ChatMembers


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

        saved_message = await self.save_message(
            self.chat_id,
            user,
            text,
            attachments,
        )

        await self.channel_layer.group_send(
            self.room_group_name,
            {
                "type": "chat_message",
                "id": saved_message.id,
                "text": saved_message.text,
                "username": user.username,
                "prof_pic": user.prof_pic.url if user.prof_pic else None,
                "timestamp": saved_message.timestamp.isoformat(),
                "attachments": saved_message.attachments,
            },
        )

    # runs for each user and the group and sends the message data back to the browser
    async def chat_message(self, event):
        await self.send(
            text_data=json.dumps(
                {
                    "id": event["id"],
                    "text": event["text"],
                    "username": event["username"],
                    "prof_pic": event["prof_pic"],
                    "timestamp": event["timestamp"],
                    "attachments": event["attachments"],
                }
            )
        )

    # saves message in the database
    @database_sync_to_async
    def is_chat_member(self, chat_id, user_id):
        return ChatMembers.objects.filter(chat_id=chat_id, user_id=user_id).exists()

    @database_sync_to_async
    def save_message(self, chat_id, user, text, attachments):
        chat = Chats.objects.get(id=chat_id)

        return Messages.objects.create(
            chat=chat,
            user=user,
            text=text,
            attachments=attachments,
        )


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
