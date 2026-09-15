import json
import tempfile
from django.test import TestCase, TransactionTestCase
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.db import IntegrityError
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from channels.testing import WebsocketCommunicator
from channels.layers import get_channel_layer
from channels.db import database_sync_to_async

from .models import Friends, FriendRequests, Chats, ChatMembers, Messages, Attachments
from .consumers import ChatConsumer, NotificationConsumer
from .message_composition import create_message_composition

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
        self.media_dir = tempfile.TemporaryDirectory()
        self.media_override = self.settings(MEDIA_ROOT=self.media_dir.name)
        self.media_override.enable()
        self.user = User.objects.create_user(username="alice", password="testpass123")
        self.chat = Chats.objects.create(
            owner=self.user, name="Test Chat", chat_type="DM"
        )
        self.message = Messages.objects.create(
            chat=self.chat, user=self.user, text="Check this out"
        )

    def tearDown(self):
        self.media_override.disable()
        self.media_dir.cleanup()

    def test_create_attachment(self):
        attachment = Attachments.objects.create(
            message=self.message,
            file=SimpleUploadedFile("test.png", b"image-data"),
        )
        self.assertTrue(attachment.file.name.endswith("test.png"))
        self.assertEqual(attachment.file.size, 10)
        self.assertEqual(attachment.message, self.message)

    def test_message_can_have_multiple_attachments(self):
        Attachments.objects.create(
            message=self.message,
            file=SimpleUploadedFile("a.png", b"a"),
        )
        Attachments.objects.create(
            message=self.message,
            file=SimpleUploadedFile("b.png", b"b"),
        )
        self.assertEqual(Attachments.objects.filter(message=self.message).count(), 2)

    def test_deleting_message_deletes_attachments(self):
        Attachments.objects.create(
            message=self.message,
            file=SimpleUploadedFile("test.png", b"image-data"),
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

class CreateFriendRequestAPIViewTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.sender = User.objects.create_user(username="alice", password="testpass123")
        self.receiver = User.objects.create_user(username="bob", password="testpass123")
        self.client.force_authenticate(user=self.sender)

    def test_create_friend_request_with_receiver_in_body(self):
        response = self.client.post(
            reverse("create_request_api"),
            data={"receiver": self.receiver.id},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(FriendRequests.objects.count(), 1)
        request = FriendRequests.objects.get()
        self.assertEqual(request.sender, self.sender)
        self.assertEqual(request.receiver, self.receiver)

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
        self.media_dir = tempfile.TemporaryDirectory()
        self.media_override = self.settings(MEDIA_ROOT=self.media_dir.name)
        self.media_override.enable()
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
            file=SimpleUploadedFile("test.png", b"attachment-data"),
        )

    def tearDown(self):
        self.media_override.disable()
        self.media_dir.cleanup()

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
        self.assertIn("name", attachment)
        self.assertIn("size", attachment)
        self.assertIn("file", attachment)

    def test_response_contains_correct_values(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.get(
            reverse("attachments_api", kwargs={"message_id": self.message.id})
        )
        attachment = response.data[0]
        self.assertEqual(attachment["message"], self.message.id)
        self.assertEqual(attachment["name"], "test.png")
        self.assertEqual(attachment["size"], 15)

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
            file=SimpleUploadedFile("b.png", b"second"),
        )
        self.client.force_authenticate(user=self.user)
        response = self.client.get(
            reverse("attachments_api", kwargs={"message_id": self.message.id})
        )
        self.assertEqual(len(response.data), 2)

    def test_member_cannot_read_attachments_from_another_chat(self):
        outsider = User.objects.create_user(username="outsider", password="pw")
        self.client.force_authenticate(user=outsider)

        response = self.client.get(
            reverse("attachments_api", kwargs={"message_id": self.message.id})
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class UnreadCountTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.sender = User.objects.create_user(
            username="unread-sender", password="testpass123"
        )
        self.receiver = User.objects.create_user(
            username="unread-receiver", password="testpass123"
        )
        self.outsider = User.objects.create_user(
            username="unread-outsider", password="testpass123"
        )
        self.chat = Chats.objects.create(
            owner=self.sender,
            name="Unread Test",
            chat_type="DM",
        )
        self.sender_membership = ChatMembers.objects.create(
            chat=self.chat,
            user=self.sender,
        )
        self.receiver_membership = ChatMembers.objects.create(
            chat=self.chat,
            user=self.receiver,
        )

    def test_new_message_increments_only_other_members(self):
        create_message_composition(
            chat_id=self.chat.id,
            author=self.sender,
            text="Hello",
            attachments=[],
        )

        self.sender_membership.refresh_from_db()
        self.receiver_membership.refresh_from_db()
        self.assertEqual(self.sender_membership.unread_count, 0)
        self.assertEqual(self.receiver_membership.unread_count, 1)

    def test_member_can_mark_own_chat_as_read(self):
        self.receiver_membership.unread_count = 4
        self.receiver_membership.save(update_fields=["unread_count"])
        self.client.force_authenticate(user=self.receiver)

        response = self.client.post(
            reverse("mark_chat_read_api", kwargs={"chat_id": self.chat.id})
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, {"chat_id": self.chat.id, "unread_count": 0})
        self.receiver_membership.refresh_from_db()
        self.assertEqual(self.receiver_membership.unread_count, 0)

    def test_non_member_cannot_mark_chat_as_read(self):
        self.receiver_membership.unread_count = 4
        self.receiver_membership.save(update_fields=["unread_count"])
        self.client.force_authenticate(user=self.outsider)

        response = self.client.post(
            reverse("mark_chat_read_api", kwargs={"chat_id": self.chat.id})
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.receiver_membership.refresh_from_db()
        self.assertEqual(self.receiver_membership.unread_count, 4)


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
        self.assertEqual(set(response.data.keys()), {"id", "username", "prof_pic"})

    def test_does_not_return_other_users_data(self):
        other_user = User.objects.create_user(username="bob", password="testpass123")
        self.client.force_authenticate(user=self.user)
        response = self.client.get(reverse("me"))
        self.assertNotEqual(response.data["id"], other_user.id)
        self.assertNotEqual(response.data["username"], "bob")


class ChatMutationAPIViewTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.owner = User.objects.create_user(username="chat-owner", password="pw")
        self.member = User.objects.create_user(username="chat-member", password="pw")
        self.chat = Chats.objects.create(
            owner=self.owner, name="Original", chat_type="Groupchat"
        )
        ChatMembers.objects.create(chat=self.chat, user=self.owner)
        ChatMembers.objects.create(chat=self.chat, user=self.member)

    def test_create_chat_adds_owner_membership(self):
        self.client.force_authenticate(user=self.owner)
        response = self.client.post(
            reverse("create_chat_api"),
            {"name": "Created", "chat_type": "DM"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(
            ChatMembers.objects.filter(
                chat_id=response.data["id"], user=self.owner
            ).exists()
        )

    def test_unauthenticated_user_cannot_create_chat(self):
        response = self.client.post(
            reverse("create_chat_api"),
            {"name": "Created", "chat_type": "DM"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_owner_can_update_chat(self):
        self.client.force_authenticate(user=self.owner)
        response = self.client.patch(
            reverse("handle_chat_api", kwargs={"chat_id": self.chat.id}),
            {"name": "Renamed"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.chat.refresh_from_db()
        self.assertEqual(self.chat.name, "Renamed")

    def test_non_owner_member_cannot_update_or_delete_chat(self):
        self.client.force_authenticate(user=self.member)
        url = reverse("handle_chat_api", kwargs={"chat_id": self.chat.id})

        self.assertEqual(
            self.client.patch(url, {"name": "Hijacked"}, format="json").status_code,
            status.HTTP_404_NOT_FOUND,
        )
        self.assertEqual(self.client.delete(url).status_code, status.HTTP_404_NOT_FOUND)
        self.assertTrue(Chats.objects.filter(pk=self.chat.id).exists())

    def test_owner_can_delete_chat(self):
        self.client.force_authenticate(user=self.owner)
        response = self.client.delete(
            reverse("handle_chat_api", kwargs={"chat_id": self.chat.id})
        )
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Chats.objects.filter(pk=self.chat.id).exists())


class ChatMembersAPIViewTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.owner = User.objects.create_user(username="members-owner", password="pw")
        self.member = User.objects.create_user(username="members-member", password="pw")
        self.new_member = User.objects.create_user(username="members-new", password="pw")
        self.outsider = User.objects.create_user(username="members-outsider", password="pw")
        self.chat = Chats.objects.create(
            owner=self.owner, name="Members", chat_type="Groupchat"
        )
        ChatMembers.objects.create(chat=self.chat, user=self.owner)
        ChatMembers.objects.create(chat=self.chat, user=self.member)

    def test_member_can_list_members(self):
        self.client.force_authenticate(user=self.member)
        response = self.client.get(
            reverse("chat_members_api", kwargs={"chat_id": self.chat.id})
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual({item["user"] for item in response.data}, {self.owner.id, self.member.id})

    def test_outsider_cannot_list_members(self):
        self.client.force_authenticate(user=self.outsider)
        response = self.client.get(
            reverse("chat_members_api", kwargs={"chat_id": self.chat.id})
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, [])

    def test_owner_can_add_members(self):
        self.client.force_authenticate(user=self.owner)
        response = self.client.post(
            reverse("create_members_api", kwargs={"chat_id": self.chat.id}),
            {"members": [self.new_member.id]},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(
            ChatMembers.objects.filter(chat=self.chat, user=self.new_member).exists()
        )

    def test_non_owner_cannot_add_members(self):
        self.client.force_authenticate(user=self.member)
        response = self.client.post(
            reverse("create_members_api", kwargs={"chat_id": self.chat.id}),
            {"members": [self.new_member.id]},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_owner_can_remove_another_member(self):
        ChatMembers.objects.create(chat=self.chat, user=self.new_member)
        self.client.force_authenticate(user=self.owner)
        response = self.client.delete(
            reverse(
                "handle_chat_members_api",
                kwargs={"chat_id": self.chat.id, "user_id": self.member.id},
            )
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(
            ChatMembers.objects.filter(chat=self.chat, user=self.member).exists()
        )

    def test_outsider_cannot_remove_member(self):
        self.client.force_authenticate(user=self.outsider)
        response = self.client.delete(
            reverse(
                "handle_chat_members_api",
                kwargs={"chat_id": self.chat.id, "user_id": self.member.id},
            )
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertTrue(ChatMembers.objects.filter(chat=self.chat, user=self.member).exists())


class FriendMutationAPIViewTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username="friend-user", password="pw")
        self.friend = User.objects.create_user(username="friend-target", password="pw")

    def test_create_friend_uses_authenticated_user(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.post(
            reverse("create_friend_api"),
            {"friend": self.friend.id},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(Friends.objects.filter(user=self.user, friend=self.friend).exists())

    def test_receiver_can_update_friend_request(self):
        friend_request = FriendRequests.objects.create(
            sender=self.friend, receiver=self.user
        )
        self.client.force_authenticate(user=self.user)
        response = self.client.patch(
            reverse("update_request_api", kwargs={"sender_id": self.friend.id}),
            {"status": "Accepted"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        friend_request.refresh_from_db()
        self.assertEqual(friend_request.status, "Accepted")

    def test_non_receiver_cannot_update_friend_request(self):
        FriendRequests.objects.create(sender=self.friend, receiver=self.user)
        outsider = User.objects.create_user(username="request-outsider", password="pw")
        self.client.force_authenticate(user=outsider)
        response = self.client.patch(
            reverse("update_request_api", kwargs={"sender_id": self.friend.id}),
            {"status": "Accepted"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class SearchAPIViewTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username="searcher", password="pw")
        self.friend = User.objects.create_user(username="matching_friend", password="pw")
        self.stranger = User.objects.create_user(username="matching_stranger", password="pw")
        Friends.objects.create(user=self.user, friend=self.friend)
        self.client.force_authenticate(user=self.user)

    def test_user_search_uses_path_query_and_excludes_existing_friends(self):
        response = self.client.get(
            reverse("search_users_api", kwargs={"q": "matching"})
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual([item["id"] for item in response.data], [self.stranger.id])

    def test_friend_search_returns_matching_friendship(self):
        response = self.client.get(
            reverse("search_friends_api", kwargs={"q": "matching"})
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["friend"], self.friend.id)


class CreateAttachmentsAPIViewTests(TestCase):
    def setUp(self):
        self.media_dir = tempfile.TemporaryDirectory()
        self.media_override = self.settings(MEDIA_ROOT=self.media_dir.name)
        self.media_override.enable()
        self.client = APIClient()
        self.user = User.objects.create_user(username="upload-user", password="pw")

    def tearDown(self):
        self.media_override.disable()
        self.media_dir.cleanup()

    def test_authenticated_user_can_upload_multiple_files(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.post(
            reverse("create_attachments_api"),
            {
                "file": [
                    SimpleUploadedFile("one.txt", b"one"),
                    SimpleUploadedFile("two.txt", b"two"),
                ]
            },
            format="multipart",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(len(response.data["attachments"]), 2)
        self.assertEqual(Attachments.objects.count(), 2)

    def test_upload_requires_a_file(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.post(reverse("create_attachments_api"), {})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_upload_requires_authentication(self):
        response = self.client.post(
            reverse("create_attachments_api"),
            {"file": SimpleUploadedFile("one.txt", b"one")},
            format="multipart",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class PageAuthenticationTests(TestCase):
    def test_chat_page_redirects_anonymous_user(self):
        response = self.client.get(reverse("chats"))
        self.assertEqual(response.status_code, status.HTTP_302_FOUND)
        self.assertIn(reverse("login"), response.url)

    def test_friend_page_redirects_anonymous_user(self):
        response = self.client.get(reverse("friends"))
        self.assertEqual(response.status_code, status.HTTP_302_FOUND)
        self.assertIn(reverse("login"), response.url)


# Helper to build a communicator with a fake scope
def make_communicator(chat_id, user):
    communicator = WebsocketCommunicator(
        ChatConsumer.as_asgi(),
        f"/ws/chat/{chat_id}/",
    )
    communicator.scope["url_route"] = {"kwargs": {"chat_id": chat_id}}
    communicator.scope["user"] = user
    return communicator


def make_notification_communicator(user):
    communicator = WebsocketCommunicator(
        NotificationConsumer.as_asgi(),
        "/ws/notifications/",
    )
    communicator.scope["user"] = user
    return communicator


class TestChatConsumerConnect(TransactionTestCase):
    async def test_connect_success(self):
        user = await User.objects.acreate_user(username="alice", password="pw")
        chat = await Chats.objects.acreate(owner=user, name="Test Chat", chat_type="DM")
        await ChatMembers.objects.acreate(chat=chat, user=user)

        comm = make_communicator(chat.id, user)
        connected, _ = await comm.connect()

        self.assertTrue(connected)
        await comm.disconnect()

    async def test_disconnect_leaves_group(self):
        user = await User.objects.acreate_user(username="bob", password="pw")
        chat = await Chats.objects.acreate(owner=user, name="Test Chat", chat_type="DM")
        await ChatMembers.objects.acreate(chat=chat, user=user)

        comm = make_communicator(chat.id, user)
        await comm.connect()
        await comm.disconnect()

        await get_channel_layer().group_send(
            f"Chat_{chat.id}",
            {
                "type": "chat_message",
                "text": "late",
                "username": "bob",
                "timestamp": "now",
                "attachments": [],
            },
        )
        self.assertTrue(await comm.receive_nothing())

    async def test_anonymous_user_is_rejected(self):
        user = await User.objects.acreate_user(username="owner", password="pw")
        chat = await Chats.objects.acreate(owner=user, name="Test Chat", chat_type="DM")

        comm = make_communicator(chat.id, AnonymousUser())
        connected, code = await comm.connect()

        self.assertFalse(connected)
        self.assertEqual(code, 4401)

    async def test_non_member_is_rejected(self):
        owner = await User.objects.acreate_user(username="owner2", password="pw")
        outsider = await User.objects.acreate_user(username="outsider2", password="pw")
        chat = await Chats.objects.acreate(owner=owner, name="Test Chat", chat_type="DM")

        comm = make_communicator(chat.id, outsider)
        connected, code = await comm.connect()

        self.assertFalse(connected)
        self.assertEqual(code, 4403)


class TestChatConsumerReceive(TransactionTestCase):
    async def test_receive_saves_and_broadcasts(self):
        user = await User.objects.acreate_user(username="carol", password="pw")
        chat = await Chats.objects.acreate(owner=user, name="Test Chat", chat_type="DM")
        await ChatMembers.objects.acreate(chat=chat, user=user)

        comm = make_communicator(chat.id, user)
        await comm.connect()

        await comm.send_to(
            text_data=json.dumps({"text": "Hello!", "attachments": []})
        )
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
        await ChatMembers.objects.acreate(chat=chat, user=user)

        comm = make_communicator(chat.id, user)
        await comm.connect()

        # Should not crash the server — connection stays open or closes cleanly
        await comm.send_to(text_data="not valid json {{")
        event = await comm.receive_output()
        self.assertEqual(event, {"type": "websocket.close", "code": 400})
        self.assertFalse(await Messages.objects.filter(chat=chat).aexists())

    async def test_receive_missing_text_key(self):
        user = await User.objects.acreate_user(username="eve", password="pw")
        chat = await Chats.objects.acreate(owner=user, name="Test Chat", chat_type="DM")
        await ChatMembers.objects.acreate(chat=chat, user=user)

        comm = make_communicator(chat.id, user)
        await comm.connect()

        await comm.send_to(text_data=json.dumps({"wrong_key": "oops"}))
        event = await comm.receive_output()
        self.assertEqual(event, {"type": "websocket.close", "code": 400})
        self.assertFalse(await Messages.objects.filter(chat=chat).aexists())


class TestChatConsumerGroupIsolation(TransactionTestCase):
    async def test_message_not_received_by_other_group(self):
        user = await User.objects.acreate_user(username="frank", password="pw")
        chat1 = await Chats.objects.acreate(
            owner=user, name="Test Chat", chat_type="DM"
        )
        chat2 = await Chats.objects.acreate(
            owner=user, name="Test Chat2", chat_type="DM"
        )
        await ChatMembers.objects.acreate(chat=chat1, user=user)
        await ChatMembers.objects.acreate(chat=chat2, user=user)

        comm1 = make_communicator(chat1.id, user)
        comm2 = make_communicator(chat2.id, user)

        await comm1.connect()
        await comm2.connect()

        await comm1.send_to(
            text_data=json.dumps({"text": "Only for chat1", "attachments": []})
        )

        response = json.loads(await comm1.receive_from())
        self.assertEqual(response["text"], "Only for chat1")

        # comm2 should receive nothing
        self.assertTrue(await comm2.receive_nothing())

        await comm1.disconnect()
        await comm2.disconnect()


class NotificationConsumerTests(TransactionTestCase):
    async def test_anonymous_user_is_rejected(self):
        comm = make_notification_communicator(AnonymousUser())
        connected, _ = await comm.connect()
        self.assertFalse(connected)

    async def test_message_sends_recipient_unread_count(self):
        sender = await User.objects.acreate_user(username="notify-sender", password="pw")
        recipient = await User.objects.acreate_user(
            username="notify-recipient", password="pw"
        )
        chat = await Chats.objects.acreate(owner=sender, name="Notify", chat_type="DM")
        await ChatMembers.objects.acreate(chat=chat, user=sender)
        await ChatMembers.objects.acreate(chat=chat, user=recipient)

        comm = make_notification_communicator(recipient)
        connected, _ = await comm.connect()
        self.assertTrue(connected)

        await database_sync_to_async(create_message_composition)(
            chat_id=chat.id,
            author=sender,
            text="one",
            attachments=[],
        )
        event = json.loads(await comm.receive_from())

        self.assertEqual(
            event,
            {"type": "unread_update", "chat_id": chat.id, "unread_count": 1},
        )
        await comm.disconnect()

    async def test_notifications_are_isolated_by_user(self):
        sender = await User.objects.acreate_user(username="iso-sender", password="pw")
        recipient = await User.objects.acreate_user(username="iso-recipient", password="pw")
        outsider = await User.objects.acreate_user(username="iso-outsider", password="pw")
        chat = await Chats.objects.acreate(owner=sender, name="Notify", chat_type="DM")
        await ChatMembers.objects.acreate(chat=chat, user=sender)
        await ChatMembers.objects.acreate(chat=chat, user=recipient)

        recipient_comm = make_notification_communicator(recipient)
        outsider_comm = make_notification_communicator(outsider)
        await recipient_comm.connect()
        await outsider_comm.connect()

        await database_sync_to_async(create_message_composition)(
            chat_id=chat.id,
            author=sender,
            text="private",
            attachments=[],
        )

        self.assertEqual(
            json.loads(await recipient_comm.receive_from())["unread_count"], 1
        )
        self.assertTrue(await outsider_comm.receive_nothing())
        await recipient_comm.disconnect()
        await outsider_comm.disconnect()
