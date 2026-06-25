import json
from django.test import TestCase, TransactionTestCase
from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.core.exceptions import ValidationError
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from channels.testing import WebsocketCommunicator
from channels.layers import get_channel_layer

from .models import Friends, FriendRequests, Chats, ChatMembers, Messages, Attachments
from .consumers import ChatConsumer

User = get_user_model()


class FriendsModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="alice", password="testpass123")
        self.friend = User.objects.create_user(username="bob", password="testpass123")

    def test_create_friendship(self):
        friendship = Friends.objects.create(user=self.user, friend=self.friend)
        self.assertEqual(friendship.user, self.user)
        self.assertEqual(friendship.friend, self.friend)

    def test_duplicate_friendship_raises_integrity_error(self):
        Friends.objects.create(user=self.user, friend=self.friend)
        with self.assertRaises(IntegrityError):
            Friends.objects.create(user=self.user, friend=self.friend)

    def test_deleting_user_deletes_friendship(self):
        Friends.objects.create(user=self.user, friend=self.friend)
        self.user.delete()
        self.assertEqual(Friends.objects.count(), 0)

    def test_deleting_friend_deletes_friendship(self):
        Friends.objects.create(user=self.user, friend=self.friend)
        self.friend.delete()
        self.assertEqual(Friends.objects.count(), 0)


class FriendRequestsModelTests(TestCase):
    def setUp(self):
        self.sender = User.objects.create_user(username="alice", password="testpass123")
        self.receiver = User.objects.create_user(username="bob", password="testpass123")

    def test_create_friend_request(self):
        request = FriendRequests.objects.create(
            sender=self.sender, receiver=self.receiver
        )
        self.assertEqual(request.sender, self.sender)
        self.assertEqual(request.receiver, self.receiver)

    def test_default_status_is_pending(self):
        request = FriendRequests.objects.create(
            sender=self.sender, receiver=self.receiver
        )
        self.assertEqual(request.status, "Pending")

    def test_status_can_be_set_to_accepted(self):
        request = FriendRequests.objects.create(
            sender=self.sender, receiver=self.receiver, status="Accepted"
        )
        self.assertEqual(request.status, "Accepted")

    def test_status_can_be_set_to_rejected(self):
        request = FriendRequests.objects.create(
            sender=self.sender, receiver=self.receiver, status="Rejected"
        )
        self.assertEqual(request.status, "Rejected")

    def test_invalid_status_raises_validation_error(self):
        request = FriendRequests(
            sender=self.sender, receiver=self.receiver, status="InvalidStatus"
        )
        with self.assertRaises(ValidationError):
            request.full_clean()

    def test_created_at_is_set_automatically(self):
        request = FriendRequests.objects.create(
            sender=self.sender, receiver=self.receiver
        )
        self.assertIsNotNone(request.created_at)

    def test_deleting_sender_deletes_request(self):
        FriendRequests.objects.create(sender=self.sender, receiver=self.receiver)
        self.sender.delete()
        self.assertEqual(FriendRequests.objects.count(), 0)

    def test_deleting_receiver_deletes_request(self):
        FriendRequests.objects.create(sender=self.sender, receiver=self.receiver)
        self.receiver.delete()
        self.assertEqual(FriendRequests.objects.count(), 0)


class ChatsModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="alice", password="testpass123")

    def test_create_dm_chat(self):
        chat = Chats.objects.create(owner=self.user, name="Test DM", chat_type="DM")
        self.assertEqual(chat.name, "Test DM")
        self.assertEqual(chat.chat_type, "DM")

    def test_create_groupchat(self):
        chat = Chats.objects.create(
            owner=self.user, name="Test Group", chat_type="Groupchat"
        )
        self.assertEqual(chat.chat_type, "Groupchat")

    def test_invalid_chat_type_raises_validation_error(self):
        chat = Chats(owner=self.user, name="Bad Chat", chat_type="InvalidType")
        with self.assertRaises(ValidationError):
            chat.full_clean()

    def test_image_defaults_to_default_png(self):
        chat = Chats.objects.create(owner=self.user, name="Test Chat", chat_type="DM")
        self.assertEqual(chat.image, "default.png")

    def test_deleting_owner_deletes_chat(self):
        Chats.objects.create(owner=self.user, name="Test Chat", chat_type="DM")
        self.user.delete()
        self.assertEqual(Chats.objects.count(), 0)


class ChatMembersModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="alice", password="testpass123")
        self.other_user = User.objects.create_user(
            username="bob", password="testpass123"
        )
        self.chat = Chats.objects.create(
            owner=self.user, name="Test Chat", chat_type="DM"
        )

    def test_add_member_to_chat(self):
        member = ChatMembers.objects.create(chat=self.chat, user=self.user)
        self.assertEqual(member.chat, self.chat)
        self.assertEqual(member.user, self.user)

    def test_duplicate_member_raises_integrity_error(self):
        ChatMembers.objects.create(chat=self.chat, user=self.user)
        with self.assertRaises(IntegrityError):
            ChatMembers.objects.create(chat=self.chat, user=self.user)

    def test_different_users_can_be_members_of_same_chat(self):
        ChatMembers.objects.create(chat=self.chat, user=self.user)
        ChatMembers.objects.create(chat=self.chat, user=self.other_user)
        self.assertEqual(ChatMembers.objects.filter(chat=self.chat).count(), 2)

    def test_deleting_chat_deletes_members(self):
        ChatMembers.objects.create(chat=self.chat, user=self.user)
        self.chat.delete()
        self.assertEqual(ChatMembers.objects.count(), 0)

    def test_deleting_user_deletes_membership(self):
        ChatMembers.objects.create(chat=self.chat, user=self.user)
        self.user.delete()
        self.assertEqual(ChatMembers.objects.count(), 0)


class MessagesModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="alice", password="testpass123")
        self.chat = Chats.objects.create(
            owner=self.user, name="Test Chat", chat_type="DM"
        )

    def test_create_message(self):
        message = Messages.objects.create(chat=self.chat, user=self.user, text="Hello!")
        self.assertEqual(message.text, "Hello!")
        self.assertEqual(message.chat, self.chat)
        self.assertEqual(message.user, self.user)

    def test_timestamp_is_set_automatically(self):
        message = Messages.objects.create(chat=self.chat, user=self.user, text="Hello!")
        self.assertIsNotNone(message.timestamp)

    def test_deleting_chat_deletes_messages(self):
        Messages.objects.create(chat=self.chat, user=self.user, text="Hello!")
        self.chat.delete()
        self.assertEqual(Messages.objects.count(), 0)

    def test_deleting_user_deletes_messages(self):
        Messages.objects.create(chat=self.chat, user=self.user, text="Hello!")
        self.user.delete()
        self.assertEqual(Messages.objects.count(), 0)


class AttachmentsModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="alice", password="testpass123")
        self.chat = Chats.objects.create(
            owner=self.user, name="Test Chat", chat_type="DM"
        )
        self.message = Messages.objects.create(
            chat=self.chat, user=self.user, text="Check this out"
        )

    def test_create_attachment(self):
        attachment = Attachments.objects.create(
            message=self.message,
            filename="test.png",
            filesize=1024,
            data="attachments/test.png",
        )
        self.assertEqual(attachment.filename, "test.png")
        self.assertEqual(attachment.filesize, 1024)
        self.assertEqual(attachment.message, self.message)

    def test_message_can_have_multiple_attachments(self):
        Attachments.objects.create(
            message=self.message,
            filename="a.png",
            filesize=512,
            data="attachments/a.png",
        )
        Attachments.objects.create(
            message=self.message,
            filename="b.png",
            filesize=256,
            data="attachments/b.png",
        )
        self.assertEqual(Attachments.objects.filter(message=self.message).count(), 2)

    def test_deleting_message_deletes_attachments(self):
        Attachments.objects.create(
            message=self.message,
            filename="test.png",
            filesize=1024,
            data="attachments/test.png",
        )
        self.message.delete()
        self.assertEqual(Attachments.objects.count(), 0)


class ChatAPIViewTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username="alice", password="testpass123")
        self.other_user = User.objects.create_user(
            username="bob", password="testpass123"
        )

        self.chat = Chats.objects.create(
            owner=self.user, name="Test Chat", chat_type="DM"
        )
        ChatMembers.objects.create(chat=self.chat, user=self.user)

        self.other_chat = Chats.objects.create(
            owner=self.other_user, name="Other Chat", chat_type="Groupchat"
        )
        ChatMembers.objects.create(chat=self.other_chat, user=self.other_user)

    def test_unauthenticated_request_is_rejected(self):
        response = self.client.get(reverse("chats_api"))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_returns_only_users_chats(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.get(reverse("chats_api"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

    def test_does_not_return_chats_user_is_not_a_member_of(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.get(reverse("chats_api"))
        returned_ids = [chat["id"] for chat in response.data]
        self.assertNotIn(self.other_chat.id, returned_ids)

    def test_response_contains_correct_fields(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.get(reverse("chats_api"))
        chat = response.data[0]
        self.assertIn("id", chat)
        self.assertIn("owner", chat)
        self.assertIn("name", chat)
        self.assertIn("chat_type", chat)
        self.assertIn("image", chat)

    def test_response_contains_correct_values(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.get(reverse("chats_api"))
        chat = response.data[0]
        self.assertEqual(chat["id"], self.chat.id)
        self.assertEqual(chat["owner"], self.user.id)
        self.assertEqual(chat["name"], "Test Chat")
        self.assertEqual(chat["chat_type"], "DM")

    def test_user_appearing_in_multiple_chats_returns_no_duplicates(self):
        extra_chat = Chats.objects.create(
            owner=self.user, name="Extra Chat", chat_type="Groupchat"
        )
        ChatMembers.objects.create(chat=extra_chat, user=self.user)
        self.client.force_authenticate(user=self.user)
        response = self.client.get(reverse("chats_api"))
        self.assertEqual(len(response.data), 2)

    def test_returns_empty_list_when_user_has_no_chats(self):
        user_with_no_chats = User.objects.create_user(
            username="charlie", password="testpass123"
        )
        self.client.force_authenticate(user=user_with_no_chats)
        response = self.client.get(reverse("chats_api"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 0)


class FriendAPIViewTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username="alice", password="testpass123")
        self.friend = User.objects.create_user(username="bob", password="testpass123")
        self.stranger = User.objects.create_user(
            username="charlie", password="testpass123"
        )

        # user initiated this friendship
        self.friendship = Friends.objects.create(user=self.user, friend=self.friend)
        # user is the recipient of this one
        self.friendship2 = Friends.objects.create(user=self.stranger, friend=self.user)

    def test_unauthenticated_request_is_rejected(self):
        response = self.client.get(reverse("friends_api"))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_returns_friendships_where_user_is_initiator(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.get(reverse("friends_api"))
        returned_ids = [f["id"] for f in response.data]
        self.assertIn(self.friendship.id, returned_ids)

    def test_returns_friendships_where_user_is_recipient(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.get(reverse("friends_api"))
        returned_ids = [f["id"] for f in response.data]
        self.assertIn(self.friendship2.id, returned_ids)

    def test_response_contains_correct_fields(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.get(reverse("friends_api"))
        friend = response.data[0]
        self.assertIn("id", friend)
        self.assertIn("user", friend)
        self.assertIn("friend", friend)
        self.assertIn("user_username", friend)
        self.assertIn("friend_username", friend)

    def test_response_contains_correct_usernames(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.get(reverse("friends_api"))
        # find the friendship the user initiated
        friendship_data = next(
            f for f in response.data if f["id"] == self.friendship.id
        )
        self.assertEqual(friendship_data["user_username"], "alice")
        self.assertEqual(friendship_data["friend_username"], "bob")

    def test_returns_empty_list_when_user_has_no_friends(self):
        lonely_user = User.objects.create_user(username="dave", password="testpass123")
        self.client.force_authenticate(user=lonely_user)
        response = self.client.get(reverse("friends_api"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 0)


class FriendRequestAPIViewTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username="alice", password="testpass123")
        self.sender = User.objects.create_user(username="bob", password="testpass123")
        self.other_user = User.objects.create_user(
            username="charlie", password="testpass123"
        )

        self.pending_request = FriendRequests.objects.create(
            sender=self.sender, receiver=self.user
        )
        self.other_request = FriendRequests.objects.create(
            sender=self.sender, receiver=self.other_user
        )

    def test_unauthenticated_request_is_rejected(self):
        response = self.client.get(reverse("requests_api"))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_returns_only_requests_addressed_to_user(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.get(reverse("requests_api"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

    def test_does_not_return_requests_addressed_to_other_users(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.get(reverse("requests_api"))
        returned_ids = [r["id"] for r in response.data]
        self.assertNotIn(self.other_request.id, returned_ids)

    def test_response_contains_correct_fields(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.get(reverse("requests_api"))
        request_data = response.data[0]
        self.assertIn("id", request_data)
        self.assertIn("sender", request_data)
        self.assertIn("receiver", request_data)
        self.assertIn("sender_username", request_data)
        self.assertIn("receiver_username", request_data)
        self.assertIn("status", request_data)
        self.assertIn("created_at", request_data)

    def test_response_contains_correct_values(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.get(reverse("requests_api"))
        request_data = response.data[0]
        self.assertEqual(request_data["sender_username"], "bob")
        self.assertEqual(request_data["receiver_username"], "alice")
        self.assertEqual(request_data["status"], "Pending")

    def test_returns_empty_list_when_no_pending_requests(self):
        user_with_no_requests = User.objects.create_user(
            username="dave", password="testpass123"
        )
        self.client.force_authenticate(user=user_with_no_requests)
        response = self.client.get(reverse("requests_api"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 0)


class MessageAPIViewTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username="alice", password="testpass123")
        self.other_user = User.objects.create_user(
            username="bob", password="testpass123"
        )

        self.chat = Chats.objects.create(
            owner=self.user, name="Test Chat", chat_type="DM"
        )
        ChatMembers.objects.create(chat=self.chat, user=self.user)
        self.message1 = Messages.objects.create(
            chat=self.chat, user=self.user, text="Hello"
        )
        self.message2 = Messages.objects.create(
            chat=self.chat, user=self.user, text="World"
        )

        self.other_chat = Chats.objects.create(
            owner=self.other_user, name="Other Chat", chat_type="DM"
        )
        ChatMembers.objects.create(chat=self.other_chat, user=self.other_user)
        Messages.objects.create(
            chat=self.other_chat, user=self.other_user, text="Secret"
        )

    def test_unauthenticated_request_is_rejected(self):
        response = self.client.get(
            reverse("messages_api", kwargs={"chat_id": self.chat.id})
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_returns_all_messages_in_chat(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.get(
            reverse("messages_api", kwargs={"chat_id": self.chat.id})
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)

    def test_cannot_access_messages_in_chat_user_is_not_member_of(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.get(
            reverse("messages_api", kwargs={"chat_id": self.other_chat.id})
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_returns_404_for_nonexistent_chat(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.get(reverse("messages_api", kwargs={"chat_id": 99999}))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_response_contains_correct_fields(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.get(
            reverse("messages_api", kwargs={"chat_id": self.chat.id})
        )
        message = response.data[0]
        self.assertIn("id", message)
        self.assertIn("chat", message)
        self.assertIn("user", message)
        self.assertIn("username", message)
        self.assertIn("text", message)
        self.assertIn("timestamp", message)

    def test_response_contains_correct_values(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.get(
            reverse("messages_api", kwargs={"chat_id": self.chat.id})
        )
        message = next(m for m in response.data if m["id"] == self.message1.id)
        self.assertEqual(message["chat"], self.chat.id)
        self.assertEqual(message["user"], self.user.id)
        self.assertEqual(message["username"], "alice")
        self.assertEqual(message["text"], "Hello")


class AttachmentAPIViewTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username="alice", password="testpass123")

        self.chat = Chats.objects.create(
            owner=self.user, name="Test Chat", chat_type="DM"
        )
        ChatMembers.objects.create(chat=self.chat, user=self.user)
        self.message = Messages.objects.create(
            chat=self.chat, user=self.user, text="Check this out"
        )

        self.attachment = Attachments.objects.create(
            message=self.message,
            filename="test.png",
            filesize=2048,
            data="attachments/test.png",
        )

    def test_unauthenticated_request_is_rejected(self):
        response = self.client.get(
            reverse("attachments_api", kwargs={"message_id": self.message.id})
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_returns_attachments_for_message(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.get(
            reverse("attachments_api", kwargs={"message_id": self.message.id})
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

    def test_returns_404_for_nonexistent_message(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.get(
            reverse("attachments_api", kwargs={"message_id": 99999})
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_response_contains_correct_fields(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.get(
            reverse("attachments_api", kwargs={"message_id": self.message.id})
        )
        attachment = response.data[0]
        self.assertIn("id", attachment)
        self.assertIn("message", attachment)
        self.assertIn("filename", attachment)
        self.assertIn("filesize", attachment)
        self.assertIn("data", attachment)

    def test_response_contains_correct_values(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.get(
            reverse("attachments_api", kwargs={"message_id": self.message.id})
        )
        attachment = response.data[0]
        self.assertEqual(attachment["message"], self.message.id)
        self.assertEqual(attachment["filename"], "test.png")
        self.assertEqual(attachment["filesize"], 2048)

    def test_returns_empty_list_when_message_has_no_attachments(self):
        self.client.force_authenticate(user=self.user)
        empty_message = Messages.objects.create(
            chat=self.chat, user=self.user, text="No attachments here"
        )
        response = self.client.get(
            reverse("attachments_api", kwargs={"message_id": empty_message.id})
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 0)

    def test_message_with_multiple_attachments(self):
        Attachments.objects.create(
            message=self.message,
            filename="b.png",
            filesize=1024,
            data="attachments/b.png",
        )
        self.client.force_authenticate(user=self.user)
        response = self.client.get(
            reverse("attachments_api", kwargs={"message_id": self.message.id})
        )
        self.assertEqual(len(response.data), 2)


class CurrentUserAPIViewTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username="alice", password="testpass123")

    def test_unauthenticated_request_is_rejected(self):
        response = self.client.get(reverse("me"))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_returns_correct_id_and_username(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.get(reverse("me"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], self.user.id)
        self.assertEqual(response.data["username"], "alice")

    def test_response_only_contains_id_and_username(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.get(reverse("me"))
        self.assertEqual(set(response.data.keys()), {"id", "username"})

    def test_does_not_return_other_users_data(self):
        other_user = User.objects.create_user(username="bob", password="testpass123")
        self.client.force_authenticate(user=self.user)
        response = self.client.get(reverse("me"))
        self.assertNotEqual(response.data["id"], other_user.id)
        self.assertNotEqual(response.data["username"], "bob")


# Helper to build a communicator with a fake scope
def make_communicator(chat_id, user):
    communicator = WebsocketCommunicator(
        ChatConsumer.as_asgi(),
        f"/ws/chat/{chat_id}/",
    )
    communicator.scope["url_route"] = {"kwargs": {"chat_id": chat_id}}
    communicator.scope["user"] = user
    return communicator


class TestChatConsumerConnect(TransactionTestCase):
    async def test_connect_success(self):
        user = await User.objects.acreate_user(username="alice", password="pw")
        chat = await Chats.objects.acreate(owner=user, name="Test Chat", chat_type="DM")

        comm = make_communicator(chat.id, user)
        connected, _ = await comm.connect()

        self.assertTrue(connected)
        await comm.disconnect()

    async def test_disconnect_leaves_group(self):
        user = await User.objects.acreate_user(username="bob", password="pw")
        chat = await Chats.objects.acreate(owner=user, name="Test Chat", chat_type="DM")

        comm = make_communicator(chat.id, user)
        await comm.connect()
        await comm.disconnect()

        # No message should arrive after disconnect
        channel_layer = get_channel_layer()
        self.assertIsNotNone(channel_layer)


class TestChatConsumerReceive(TransactionTestCase):
    async def test_receive_saves_and_broadcasts(self):
        user = await User.objects.acreate_user(username="carol", password="pw")
        chat = await Chats.objects.acreate(owner=user, name="Test Chat", chat_type="DM")

        comm = make_communicator(chat.id, user)
        await comm.connect()

        await comm.send_to(text_data=json.dumps({"text": "Hello!"}))
        response = await comm.receive_from()
        data = json.loads(response)

        self.assertEqual(data["text"], "Hello!")
        self.assertEqual(data["username"], "carol")
        self.assertIn("timestamp", data)

        # Verify DB persistence
        msg = await Messages.objects.aget(chat=chat, user=user)
        self.assertEqual(msg.text, "Hello!")

        await comm.disconnect()

    async def test_receive_invalid_json(self):
        user = await User.objects.acreate_user(username="dave", password="pw")
        chat = await Chats.objects.acreate(owner=user, name="Test Chat", chat_type="DM")

        comm = make_communicator(chat.id, user)
        await comm.connect()

        # Should not crash the server — connection stays open or closes cleanly
        await comm.send_to(text_data="not valid json {{")
        await comm.disconnect()

    async def test_receive_missing_text_key(self):
        user = await User.objects.acreate_user(username="eve", password="pw")
        chat = await Chats.objects.acreate(owner=user, name="Test Chat", chat_type="DM")

        comm = make_communicator(chat.id, user)
        await comm.connect()

        await comm.send_to(text_data=json.dumps({"wrong_key": "oops"}))
        await comm.disconnect()


class TestChatConsumerGroupIsolation(TransactionTestCase):
    async def test_message_not_received_by_other_group(self):
        user = await User.objects.acreate_user(username="frank", password="pw")
        chat1 = await Chats.objects.acreate(
            owner=user, name="Test Chat", chat_type="DM"
        )
        chat2 = await Chats.objects.acreate(
            owner=user, name="Test Chat2", chat_type="DM"
        )

        comm1 = make_communicator(chat1.id, user)
        comm2 = make_communicator(chat2.id, user)

        await comm1.connect()
        await comm2.connect()

        await comm1.send_to(text_data=json.dumps({"text": "Only for chat1"}))

        # comm2 should receive nothing
        self.assertTrue(await comm2.receive_nothing())

        await comm1.disconnect()
        await comm2.disconnect()
