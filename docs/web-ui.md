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

## Security notes

Keep the Web UI bound to `127.0.0.1` unless there is a clear authorized need for remote access. Do not expose the console with default credentials.
