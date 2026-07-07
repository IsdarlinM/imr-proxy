# Security Policy

imr-proxy is for authorized security assessments, internal audits, bug bounty scopes, lab environments, developer debugging, QA testing, and defensive validation only.

It must not be used for unauthorized interception, malware, credential theft, phishing, stealth, persistence, brute force, destructive activity, or bypassing controls.

Safe defaults:

- Binds to `127.0.0.1`.
- Remote binding requires `--allow-remote`.
- HTTPS interception is opt-in.
- TLS passthrough is available.
- Secret redaction is enabled by default.
- Body capture is size-limited.
- CA installation is never automatic.

If the local CA private key is exposed, remove the CA from trust stores and run `imr-proxy ca rotate`.
