# Architecture

imr-proxy wraps mitmproxy with custom addons, SQLite persistence, findings, reporting, and FastAPI.

## References

- OWASP ASVS
- OWASP WSTG
- OWASP Secure Headers Project
- MDN HTTP headers
- mitmproxy documentation
- Python cryptography documentation

## Real-time Web console updates

Flow commits increment `traffic_revision` in the same SQLite transaction. After commit, `FlowRepository` publishes the committed revision through a thread-safe in-process event bus. The Web UI runs in a separate thread, and each authenticated `/ws/traffic` connection subscribes with an asyncio queue attached to its own event loop.

The WebSocket sends change notifications rather than duplicating filter logic. On notification, the browser reloads the current server-side filtered view from `/api/flows`. A low-frequency SQLite revision check catches writes made by another process, and the browser uses polling only while the WebSocket is unavailable.
