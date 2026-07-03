# Security and Encryption

Nimbus encrypts every vault with **AES-256**. Data is encrypted in transit with
TLS 1.3 and encrypted at rest on Nimbus servers. Pro and Team users can
additionally enable **end-to-end encryption (E2EE)**, which encrypts note
contents with a key derived from the user's passphrase so that Nimbus servers
store only ciphertext and never see the plaintext.

Enabling E2EE has an important trade-off: because Nimbus cannot see the
plaintext, it cannot recover your notes if you forget your passphrase. When you
turn on E2EE, Nimbus generates a one-time **recovery key** and requires you to
save it. The recovery key is the only way to regain access if the passphrase is
lost; without it, E2EE notes are unrecoverable.

Accounts support two-factor authentication via TOTP authenticator apps or
hardware security keys (WebAuthn). Team plans can enforce 2FA for all members
from the admin console.

E2EE has two limitations. First, server-side full-text search cannot index
end-to-end encrypted notes, so search over E2EE notebooks runs on-device only.
Second, public page publishing is disabled for E2EE notebooks, because
publishing would require the server to read the note contents.
