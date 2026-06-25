import json
import asyncio

from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async

from .models import Chats, Messages


class ChatConsumer(AsyncWebsocketConsumer):
    # gets chat id from url and adds user to appropriate group in channel then connects
    async def connect(self):
        self.chat_id = self.scope["url_route"]["kwargs"]["chat_id"]
        self.room_group_name = f"Chat_{self.chat_id}"

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
        except (json.JSONDecodeError, KeyError):
            await self.close(code=400)
            return

        user = self.scope["user"]

        # saves message to database
        saved_message = await self.save_message(
            self.chat_id,
            user,
            text,
        )

        # sends message to the group
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                "type": "chat_message",
                "text": saved_message.text,
                "username": user.username,
                "timestamp": saved_message.timestamp.isoformat(),
            },
        )

    # runs for each user and the group and sends the message data back to the browser
    async def chat_message(self, event):
        await self.send(
            text_data=json.dumps(
                {
                    "text": event["text"],
                    "username": event["username"],
                    "timestamp": event["timestamp"],
                }
            )
        )

    # saves message in the database
    @database_sync_to_async
    def save_message(self, chat_id, user, text):
        chat = Chats.objects.get(id=chat_id)

        return Messages.objects.create(
            chat=chat,
            user=user,
            text=text,
        )
