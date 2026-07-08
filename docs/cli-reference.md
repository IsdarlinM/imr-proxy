# CLI Reference

Commands include start, ca, config, sessions, report, replay, and rules test.

## References

- OWASP ASVS
- OWASP WSTG
- OWASP Secure Headers Project
- MDN HTTP headers
- mitmproxy documentation
- Python cryptography documentation


## User commands

```bash
imr-proxy users list
imr-proxy users create USERNAME --password PASSWORD [--admin]
imr-proxy users passwd USERNAME --password PASSWORD
imr-proxy users enable USERNAME
imr-proxy users disable USERNAME
imr-proxy users delete USERNAME --yes
```

These commands manage Web UI/API users in the configured SQLite storage. If `--password` is omitted for `create` or `passwd`, the CLI prompts securely.
