---
status: accepted
date: 2026-09-14
---

# Compose messages atomically with owned attachments

Message Composition is created and edited through one authenticated multipart HTTP write path behind a deep module, while WebSocket is reserved for post-commit live events. Attachments are relational records owned by exactly one Message and retrieved through Chat-membership authorization; embedded attachment JSON and direct public media access are retired. This was chosen over staged upload identifiers and dual HTTP/WebSocket writes to keep text and files atomic, make retries idempotent, preserve one canonical Message projection, and concentrate authorization and invariants; live broadcast is intentionally best-effort, and deletion retains only a non-visible Message Tombstone.
