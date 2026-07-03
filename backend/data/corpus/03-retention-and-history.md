# Data Retention and Version History

Every save creates a new version of a note. Nimbus keeps version history for
**30 days** on the Free plan and **365 days** on the Pro and Team plans. Within
the retention window you can open a note's history, preview any past version
side by side with the current one, and restore it. Restoring a version does not
delete newer versions — it creates a new version identical to the one you
restored, so history is always append-only.

When you delete a note it moves to **Trash**, where it stays recoverable for
**30 days** before it is permanently purged. Emptying the Trash manually purges
items immediately and cannot be undone. Deleting an entire notebook moves all of
its notes to Trash under the same 30-day window.

Attachments follow the note that references them. If every note referencing an
attachment is permanently purged, the attachment's storage is reclaimed during
the next nightly cleanup, typically within 24 hours.

Team administrators can set a **legal hold** on a notebook, which suspends both
the version-history window and the Trash purge for every note in that notebook
until the hold is lifted. Legal holds override the normal retention limits and
are recorded in the audit log.
