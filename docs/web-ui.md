# Web UI

The imr-proxy Web UI is available on the configured web host and port, by default `http://127.0.0.1:7414/`. The proxy listener, by default `127.0.0.1:7413`, is not a web page; configure it as your browser/system HTTP and HTTPS proxy.

## Login

The console requires authentication. On first run, when the SQLite user database is empty, imr-proxy creates the default user:

```text
admin:admin
```

Change this password immediately from **Users** or with:

```bash
imr-proxy users passwd admin --password "NewStrongPassword"
```

## User management

Administrators can create users in the `/users` page. The same workflow is available from terminal:

```bash
imr-proxy users list
imr-proxy users create analyst01 --password "ChangeMe123!"
imr-proxy users create admin02 --admin --password "ChangeMe123!"
imr-proxy users passwd analyst01 --password "NewPass123!"
imr-proxy users disable analyst01
imr-proxy users enable analyst01
imr-proxy users delete analyst01 --yes
```

Passwords are stored as PBKDF2-HMAC-SHA256 hashes with random salts. Web sessions are stored in SQLite as SHA-256 token hashes and the browser receives only an HttpOnly `SameSite=Lax` cookie.

## Pages

- Dashboard: traffic metrics, endpoint hints, searchable flow table.
- Flow detail: request/response headers and body text with redaction.
- Certificates: local CA status and explicit export commands.
- Settings: resolved runtime configuration.
- Users: local console user database.


## Live traffic lifecycle

The dashboard is no longer a static snapshot. It refreshes authenticated `/api/flows` data automatically and updates rows by stable flow ID. This prevents a request from disappearing between its request and response stages.

Recorded event types include:

- `http`: pending, complete, or error HTTP request lifecycle.
- `connect`: explicit HTTP CONNECT tunnel used by HTTPS proxy clients.
- `connection`: outbound server TCP/TLS connection lifecycle.
- `websocket`: active and closed WebSocket connection metadata.

In passthrough mode, CONNECT and connection rows expose the destination host and port only. Encrypted inner HTTPS paths require authorized interception with the local CA installed manually.

## Advanced filters

The dashboard provides server-side filtering and pagination for:

- search across URL, host, method, error text, and stored redacted flow data;
- host and method;
- exact HTTP status and status class;
- event type and lifecycle state;
- finding severity and whether findings exist;
- intercepted HTTPS, passthrough TLS/CONNECT, or plain HTTP;
- session;
- minimum and maximum duration;
- start and end time;
- row limit and sort order.

The browser stores filter selections locally. The filter chips remove individual constraints, **Reset filters** returns to defaults, and **Pause live** stops automatic refresh while reviewing older pages.

## Security notes

Keep the Web UI bound to `127.0.0.1` unless there is a clear authorized need for remote access. Do not expose the console with default credentials.
## Mobile and tablet layout

The Web UI uses a responsive layout. Below 1100 CSS pixels, the fixed desktop sidebar becomes a sticky top navigation bar. Below 700 pixels, traffic and user tables render as labeled cards, forms and panels become single-column, and typography/padding are reduced. Endpoint values, URLs, usernames, findings, commands, and JSON content use safe wrapping or contained scrolling to prevent horizontal page overflow. Static CSS and JavaScript URLs include a cache-busting revision suffix so browsers do not reuse the earlier desktop-only assets after an upgrade.

