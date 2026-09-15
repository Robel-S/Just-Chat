# PRD: Atomic Message Composition and Owned Attachments

## 1. Summary

Just-Chat will replace its split attachment-upload and WebSocket message-submission flow with one authenticated, atomic Message Composition flow. Text and files will be created or edited together through HTTP, while WebSocket remains responsible for post-commit live events.

Each Attachment will be a relational record owned by exactly one Message. Message history, mutation responses, and live events will share one canonical projection. The work also adds author-only Message editing, invisible deletion backed by an internal Message Tombstone, retry safety, protected file delivery, and consistent validation.

This PRD implements [ADR-0001](../adr/0001-compose-messages-with-owned-attachments.md).

## 2. Problem Statement

The current implementation represents attachments twice:

- `Attachments` rows may exist without a Message.
- `Messages.attachments` stores client-provided JSON independently of those rows.

The browser first uploads files and then sends returned metadata through WebSocket. A failed second step leaves orphaned rows and files, and a malicious client can submit arbitrary attachment metadata. The relational attachment endpoint and Message history can therefore describe different states.

Message persistence, unread accounting, serialization, and broadcasting are also distributed across views, a WebSocket consumer, a model signal, and browser orchestration. This makes atomicity, authorization, retries, editing, deletion, and projection consistency difficult to enforce through one test surface.

## 3. Target Users

- **Chat Members** who send Messages containing text, attachments, or both.
- **Message authors** who edit or delete their own Messages while they remain Chat Members.
- **Other Chat Members** who receive consistent live updates and retrieve authorized attachments.
- **Maintainers** who need one place to understand and verify Message Composition behavior.

## 4. Goals and Success Criteria

### Goals

- Make Message creation and editing atomic across text and attachments.
- Establish relational Attachment ownership as the single source of truth.
- Enforce Chat membership and Message authorship on every relevant operation.
- Make create, edit, and delete operations safe to retry.
- Use one canonical Message projection for history, mutation responses, and live events.
- Remove deleted Messages from all visible Chat history while retaining an internal synchronization record.
- Concentrate behavior behind one Message Composition interface with thin HTTP and WebSocket adapters.

### Success criteria

- No successful Message references unowned or client-invented attachment metadata.
- A failed composition creates no Message, Attachment row, or retained file.
- History and live delivery produce equivalent Message data.
- Duplicate create requests with the same valid idempotency key produce one Message.
- Unauthorized users cannot create, edit, delete, list, or download protected Message content.
- All acceptance criteria in section 15 pass through automated tests or explicit manual verification.

## 5. Non-Goals

- Cloud or object storage.
- A generalized storage interface before a second storage adapter exists.
- Guaranteed WebSocket delivery or a transactional outbox.
- Malware scanning.
- Attachment revision history.
- Message revision history beyond the latest content and an edit timestamp.
- Editing or deleting another user's Message, including by the Chat owner.
- Retaining deleted Message text or file content.

## 6. Assumptions

- The application remains a same-origin Django, Django REST Framework, Django Channels, and React application.
- PostgreSQL remains the relational store and local filesystem storage remains the file implementation.
- Existing `Messages.attachments` JSON is development data and may be discarded during migration.
- Existing relational Attachments linked to Messages must be preserved.
- Existing orphaned Attachment rows and their files may be deleted.
- Existing Messages receive migration-safe default version and idempotency values.
- Profile and Chat images are outside this PRD; only Message Attachments require protected delivery.

## 7. User Stories / Primary Workflows

### 7.1 Create a Message

1. A current Chat Member enters text, selects up to five allowed files, or does both.
2. The browser submits one multipart HTTP request with an idempotency key.
3. The Message Composition module validates membership, text, files, and the retry key.
4. The module persists the Message and owned Attachments atomically.
5. After commit, the server attempts to publish a versioned `message.created` event.
6. The HTTP response renders immediately for the sender; a matching live event is deduplicated by Message ID and version.

### 7.2 Retry Message creation

1. The browser retries after losing or timing out on a response.
2. The same author, Chat, idempotency key, and content return the original Message.
3. Reusing the key with different content is rejected as a conflict.

### 7.3 Edit a Message

1. The author, while still a current Chat Member, submits replacement text, retained Attachment IDs, optional new files, and the expected Message version.
2. The complete resulting Message must still contain text, at least one Attachment, or both.
3. The update succeeds atomically, increments the version, records `edited_at`, deletes removed Attachment rows and files, and publishes `message.updated` after commit.
4. A stale version is rejected without changing the Message.

### 7.4 Delete a Message

1. The author, while still a current Chat Member, requests deletion with the expected Message version.
2. Text and Attachments are removed, stored files are deleted, and the Message becomes an internal Message Tombstone.
3. The Message disappears from visible history for every user, including its author.
4. Connected browsers receive `message.deleted` and remove the Message.
5. Repeating the deletion returns the existing tombstone outcome without creating another state transition.

### 7.5 View or download an Attachment

1. A current Chat Member requests an Attachment through an authenticated route.
2. The server verifies current membership in the owning Message's Chat.
3. Supported images are delivered inline; PDF and plain-text files are downloaded using their original filename.

## 8. Functional Requirements

### Message creation

- **FR-1:** The system must accept Message Composition through one authenticated multipart HTTP write path.
- **FR-2:** Only a current Chat Member may create a Message in that Chat.
- **FR-3:** Text must be trimmed, may be empty only when at least one Attachment exists, and must not exceed 1,000 characters.
- **FR-4:** A composition may contain at most five Attachments.
- **FR-5:** Each Attachment must not exceed 10 MiB.
- **FR-6:** Allowed types are JPEG, PNG, WebP, PDF, and plain text. Validation must use server-observed content rather than trusting the browser-provided filename or content type alone.
- **FR-7:** If any part of validation or persistence fails, the complete composition must fail and leave no retained Message, Attachment row, or file.
- **FR-8:** Every created Attachment must be owned by exactly one Message at creation time; nullable or standalone Attachments are not valid application state.

### Idempotency

- **FR-9:** Creation must require a client-generated idempotency key scoped to the author and Chat.
- **FR-10:** Replaying the same key with equivalent normalized content must return the original canonical Message without creating additional rows or files.
- **FR-11:** Replaying the same key with different normalized content must return a conflict response.

### Message editing

- **FR-12:** Only the Message author may edit it, and the author must still be a current Chat Member.
- **FR-13:** Editing may replace text, retain or remove existing Attachments, and add new Attachments in one multipart request.
- **FR-14:** The resulting Message must satisfy the same text, count, size, and type rules as creation.
- **FR-15:** Editing must require the expected Message version and reject stale versions as conflicts.
- **FR-16:** A successful edit must increment the Message version and record `edited_at`.
- **FR-17:** Only the latest Message content is retained; previous text and Attachment revisions are not stored.

### Message deletion

- **FR-18:** Only the Message author may delete it, and the author must still be a current Chat Member.
- **FR-19:** Deletion must require the expected Message version.
- **FR-20:** Deletion must remove Message text, all Attachment rows, and all corresponding stored files.
- **FR-21:** Deletion must retain a non-visible Message Tombstone containing only synchronization and identity data.
- **FR-22:** Message Tombstones must be excluded from visible Chat history for all users, including the author.
- **FR-23:** Repeated deletion must return the existing deletion outcome without producing another transition.

### Projection and live delivery

- **FR-24:** Message history, successful create/edit responses, and create/edit live events must use the same canonical Message projection.
- **FR-25:** Live events must use one versioned envelope with event type and either the canonical Message projection or a non-visible deletion projection.
- **FR-26:** WebSocket must not accept Message creation or mutation commands after migration; it is server-to-browser delivery only for this feature.
- **FR-27:** Live events must be attempted only after the database transaction commits.
- **FR-28:** A WebSocket publishing failure must not roll back or report failure for an already committed HTTP mutation.
- **FR-29:** Browser state must deduplicate create/update events by Message ID and version.
- **FR-30:** Only newly created Messages increment unread counts; edits and deletions do not.

### Protected Attachment delivery

- **FR-31:** Attachments must be stored outside any directly served public-media path.
- **FR-32:** Only a current member of the owning Message's Chat may retrieve an Attachment.
- **FR-33:** Supported images must use inline content disposition; other allowed types must use attachment disposition.
- **FR-34:** Download responses must use the preserved original filename without exposing the generated storage name.
- **FR-35:** Deleted Attachments and Attachments belonging to Message Tombstones must not be retrievable.

### Migration

- **FR-36:** Preserve existing relational Attachment rows that already reference a Message.
- **FR-37:** Delete existing orphaned Attachment rows and their stored files.
- **FR-38:** Discard legacy `Messages.attachments` JSON and remove the field after migration.
- **FR-39:** Existing Messages must receive valid initial version state; migrated rows without idempotency keys must remain readable.

## 9. Non-Functional Requirements

- **NFR-1 — Atomicity:** Database mutations for one composition must execute in one transaction. Files written before a failed transaction must be cleaned up.
- **NFR-2 — Security:** Authorization must be enforced server-side for every mutation and file read. Client-provided ownership, paths, filenames, content types, or attachment metadata must not be trusted.
- **NFR-3 — Privacy:** Protected Attachments must not be reachable through Django's public development media route or any exposed filesystem URL.
- **NFR-4 — Consistency:** Live events must describe committed state and use the same field meanings as history responses.
- **NFR-5 — Retry safety:** Network retries must not duplicate Messages or mutation effects.
- **NFR-6 — File safety:** Generated storage names must prevent collisions and path traversal; download responses must set `X-Content-Type-Options: nosniff`.
- **NFR-7 — Testability:** Domain behavior must be testable through the Message Composition interface without invoking HTTP or WebSocket machinery.
- **NFR-8 — Observability:** Best-effort live-publication failures and file-cleanup failures must be logged with Message/Chat identifiers but without Message text or file content.
- **NFR-9 — Compatibility:** Existing visible text Messages must remain readable after migration.

## 10. UX / API / Interface Requirements

### HTTP writes

The intended resource shape is:

- `POST /api/chats/<chat_id>/messages/` — create a Message Composition.
- `PATCH /api/messages/<message_id>/` — edit the complete Message Composition.
- `DELETE /api/messages/<message_id>/` — delete and return the non-visible deletion outcome.
- `GET /api/attachments/<attachment_id>/download/` — authorize and deliver an Attachment.

The existing history route may be retained or aliased during migration, but its response must adopt the canonical projection.

Creation uses an `Idempotency-Key` request header. Editing and deletion include the caller's expected Message version. Multipart edit requests explicitly identify retained Attachment IDs; any current Attachment not retained is removed when the edit commits.

Expected failure classes:

- `400` for malformed or empty compositions.
- `403` when an authenticated user is not permitted to perform the operation.
- `404` when the Chat, Message, or Attachment should not be disclosed to the caller.
- `409` for idempotency-content conflicts or stale Message versions.
- `413` when request or file size limits are exceeded.
- `415` for unsupported file content.

### Canonical Message projection

Create, edit, history, and corresponding live events expose the same fields:

- Message ID and Chat ID.
- Author ID, username, and profile-image reference.
- Normalized text.
- Creation timestamp and nullable edit timestamp.
- Current version.
- Ordered Attachments containing Attachment ID, original filename, verified content type, byte size, and authorized download URL.

The browser renders the successful HTTP response immediately and ignores a live event whose Message ID and version are already present.

### Live event envelope

The event envelope distinguishes `message.created`, `message.updated`, and `message.deleted`. Create and update carry the canonical Message projection. Delete carries only the Message ID, Chat ID, resulting version, and deletion timestamp required to remove local state.

### Browser behavior

- Preserve the current draft and selected files after validation, authorization, network, or server failure.
- Clear the draft only after a successful HTTP response.
- Display actionable validation messages for count, size, type, empty content, and stale edits.
- Remove a deleted Message without displaying a deletion marker.
- Continue rendering authorized JPEG, PNG, and WebP Attachments inline.

## 11. Data Model / State Changes

### Message

The Message model requires:

- Removal of embedded attachment JSON.
- A nullable idempotency key for migrated rows and a uniqueness rule scoped to author and Chat when present.
- A version initialized for existing and new Messages.
- A nullable `edited_at` timestamp.
- A nullable deletion timestamp or equivalent tombstone state.
- Text capable of becoming empty when a Message becomes a tombstone.

### Attachment

The Attachment model requires:

- A non-null owning Message relationship after migration.
- A generated storage name independent of the original filename.
- Persisted original filename, verified content type, and byte size.
- A clear reverse relationship from Message to Attachments.
- Storage outside the publicly served media tree.

### State transitions

- **Create:** no record → active Message version 1 with zero to five owned Attachments.
- **Edit:** active Message version N → active Message version N+1 with replacement composition.
- **Delete:** active Message version N → non-visible Message Tombstone version N+1 with no text or Attachments.
- **Repeated delete:** Message Tombstone version N → unchanged Message Tombstone version N.

Message Tombstones are excluded from visible history queries but retained for identity, version checks, synchronization, and idempotent deletion.

## 12. Permissions, Privacy, and Security

- Authentication is required for all Message and Attachment operations.
- Current Chat membership is required for Message creation, history access, and Attachment access.
- Current Chat membership plus authorship is required for Message editing and deletion.
- Chat ownership grants no additional authority over another author's Message.
- Leaving a Chat revokes access to its Message history, Attachments, and mutation operations, including for Messages the former member authored.
- Attachment ownership is derived from server-side relationships, never from submitted Chat or Message metadata.
- Filenames must be normalized for response headers and must not influence filesystem paths.
- Type checks must not trust filename extensions alone.
- Responses should avoid revealing whether inaccessible Messages or Attachments exist.

## 13. Edge Cases and Failure Modes

- Text containing only whitespace with no files is rejected.
- Attachment-only Messages remain valid.
- Removing the last Attachment while leaving blank text is rejected.
- An edit containing retained plus new Attachments is rejected when the resulting count exceeds five.
- A new file failing validation causes the whole create or edit to fail; existing Message state remains unchanged.
- A database failure after file writes triggers cleanup of newly written files.
- File cleanup failure is logged and must not expose the file through a public route.
- A duplicate idempotency key with equivalent normalized content returns the original Message.
- A duplicate idempotency key with different text or files returns a conflict.
- A stale edit or delete returns a conflict and the current version without leaking inaccessible content.
- An author who leaves the Chat can no longer edit or delete their prior Messages.
- A WebSocket event arriving before the browser processes its HTTP response does not create a duplicate.
- A missed live event is corrected when history is next loaded.
- Repeated deletion does not recreate events, increment versions, or affect unread counts.
- A Message Tombstone never appears in visible history or search results.
- Concurrent download and deletion may finish an already-authorized response, but subsequent requests must fail.

## 14. Risks

- **Filesystem/database mismatch:** File storage is not transactional with PostgreSQL. Explicit cleanup paths and tests are required.
- **Migration data loss:** Legacy JSON and orphaned development files are intentionally discarded. The migration must report counts so unexpected volume is visible before removal.
- **Direct-media leakage:** Keeping Attachments beneath a publicly served media root would invalidate membership checks even if generated URLs are hidden.
- **Event duplication or reordering:** HTTP responses and live events race. Message ID plus version must determine whether browser state applies an event.
- **Best-effort delivery gaps:** Other connected users may miss a live event when channel publication fails. History remains authoritative by design.
- **Content detection limits:** Server-side type validation reduces spoofing but is not malware detection; malware scanning remains explicitly out of scope.
- **Large multipart requests:** Five 10 MiB files permit a 50 MiB composition plus overhead. Deployment request limits must accommodate or deliberately reject that maximum.

## 15. Acceptance Criteria

- **AC-1 (FR-1–FR-8):** A current Chat Member can create text-only, Attachment-only, and combined Messages in one request; any invalid part leaves no retained state.
- **AC-2 (FR-2, FR-31–FR-35):** A non-member receives no Message or Attachment content and cannot access a file through a direct public URL.
- **AC-3 (FR-4–FR-6):** The server rejects a sixth Attachment, a file larger than 10 MiB, and content outside the allowlist.
- **AC-4 (FR-9–FR-11):** Equivalent retries create one Message; changed content under the same key returns `409`.
- **AC-5 (FR-12–FR-17):** A current author can atomically edit text and Attachments; another user, a former Chat Member, and a stale version cannot.
- **AC-6 (FR-18–FR-23):** Deletion removes visible content and stored files, retains one internal tombstone, and is idempotent.
- **AC-7 (FR-24–FR-29):** History, HTTP responses, and live events agree field-for-field; sender-side deduplication prevents duplicate rendering.
- **AC-8 (FR-27–FR-28):** No live event is emitted for a rolled-back mutation, and publication failure does not undo committed state.
- **AC-9 (FR-30):** Creation increments unread counts for other Chat Members; editing and deletion do not.
- **AC-10 (FR-36–FR-39):** Migration preserves linked relational Attachments and readable text Messages while removing orphan rows, files, and legacy JSON.
- **AC-11 (NFR-6):** Generated storage paths do not contain the original filename, while authorized downloads preserve the original display name and set `nosniff`.
- **AC-12 (UX):** Failed submissions preserve the browser draft and selected files; successful submissions clear them.
- **AC-13 (Deletion UX):** Deleted Messages disappear for the author and all other connected Chat Members without a visible marker.

## 16. Implementation Outline

1. Add focused tests for the Message Composition interface covering validation, atomicity, permissions, idempotency, versions, tombstones, and projection parity.
2. Introduce the Message and Attachment schema needed for ownership, metadata, idempotency, versions, editing, and tombstones.
3. Add a data migration that reports and removes orphaned Attachments, preserves linked rows, initializes Message state, and retires embedded JSON.
4. Move Message creation, editing, deletion, Attachment association, unread updates, and canonical projection behind one deep module.
5. Add authenticated multipart HTTP adapters and protected Attachment delivery.
6. Publish versioned live events after commit and remove Message submission from the WebSocket consumer.
7. Update the React chat flow to submit multipart HTTP requests, render canonical responses, deduplicate live events, and support edit/delete interactions.
8. Replace tests coupled to separate upload, signal, and WebSocket write paths with interface-level tests plus thin adapter tests.
9. Verify migration behavior against a copy of current development data, including file cleanup and inaccessible direct paths.

## 17. Open Questions

### Blocking

None. Product and architecture decisions required for implementation are settled by ADR-0001 and the architecture review.

### Non-blocking

- Should the existing Message-history URL be retained as a compatibility alias or renamed with the new resource layout?
- Which content-inspection library should verify file types in the current Python environment?
- Should file-cleanup failures receive a future reconciliation command if operational evidence shows they occur?

These questions may be resolved during implementation without changing the product behavior defined here.

## 18. Suggested Next Step

Review this PRD for approval, then convert it into vertically sliced execution issues with dependencies and acceptance criteria. Use the repository's GitHub issue-tracker configuration for publication.
