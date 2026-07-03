# Nimbus Overview

Nimbus is a cross-platform notes and file-sync application. It keeps a single
encrypted vault of notes, documents, and attachments in sync across a user's
devices — macOS, Windows, Linux, iOS, and Android — and exposes the same vault
through a web app and a public HTTP API.

The core object in Nimbus is a **note**. A note has a title, a Markdown body,
optional attachments, and a set of tags. Notes live inside **notebooks**, and a
notebook can be shared with other Nimbus users or published as a read-only
public page. Every change to a note is versioned, so edits can be reviewed and
rolled back.

Sync is conflict-free: Nimbus uses a per-note operational-transform log, so two
devices editing the same note offline will merge cleanly when they reconnect
rather than creating "conflicted copy" duplicates. If an automatic merge is ever
ambiguous, Nimbus keeps both edits as adjacent blocks and flags the note for
review instead of silently dropping a change.

Nimbus is offline-first. The full vault is cached on each device, so search,
editing, and browsing all work with no network connection; changes queue locally
and sync when connectivity returns.
