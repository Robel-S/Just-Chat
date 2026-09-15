# Just-Chat

Just-Chat is a private conversation space where users exchange messages with other members of a chat.

## Language

**Chat**:
A private conversation whose current members can read its history and attachments.
_Avoid_: Room, channel, thread

**Chat Member**:
A user who currently belongs to a Chat and may participate in it.
_Avoid_: Participant, subscriber

**Message**:
A history entry authored by one Chat Member. An active Message contains text, attachments, or both; a deleted Message remains as a Message Tombstone.
_Avoid_: Post, chat message

**Message Tombstone**:
The non-visible record retained after an author deletes a Message. It preserves identity for synchronization but contains no Message text or attachments.
_Avoid_: Deleted record, hidden message

**Attachment**:
A file owned by exactly one Message. Its visibility follows that Message's Chat membership.
_Avoid_: Upload, media item

**Message Composition**:
The complete text-and-attachment content submitted together to become one Message.
_Avoid_: Payload, draft bundle
