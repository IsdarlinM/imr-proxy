# imr-proxy

```text
██╗███╗   ███╗██████╗       ██████╗ ██████╗  ██████╗ ██╗  ██╗██╗   ██╗
██║████╗ ████║██╔══██╗      ██╔══██╗██╔══██╗██╔═══██╗╚██╗██╔╝╚██╗ ██╔╝
██║██╔████╔██║██████╔╝█████╗██████╔╝██████╔╝██║   ██║ ╚███╔╝  ╚████╔╝
██║██║╚██╔╝██║██╔══██╗╚════╝██╔═══╝ ██╔══██╗██║   ██║ ██╔██╗   ╚██╔╝
██║██║ ╚═╝ ██║██║  ██║      ██║     ██║  ██║╚██████╔╝██╔╝ ██╗   ██║
╚═╝╚═╝     ╚═╝╚═╝  ╚═╝      ╚═╝     ╚═╝  ╚═╝ ╚═════╝ ╚═╝  ╚═╝   ╚═╝
Defensive HTTP/HTTPS Inspection Proxy
Version: 0.1.6
```

imr-proxy is a professional defensive HTTP/HTTPS inspection proxy for authorized security assessments, internal audits, QA testing, developer debugging, lab environments, and bug bounty scopes.

## Authorized use notice

Use this tool only on systems you own or are explicitly authorized to test. Do not use it for unauthorized interception, credential theft, phishing, malware, persistence, stealth, brute force, destructive behavior, or bypassing controls.

## Features

- Forward proxy mode using mitmproxy.
- HTTP proxying and HTTPS CONNECT support.
- Optional HTTPS interception with local private CA.
- TLS passthrough mode when interception is disabled.
- Upstream proxy and proxy authentication options.
- Domain allowlist, blocklist, path/method/header/cookie-oriented filtering primitives.
- Request/response capture with body size limits.
- Binary body detection.
- Redirect tracking.
- Timing metrics.
- WebSocket visibility when supported by mitmproxy.
- HTTP/1.1 and HTTP/2 through mitmproxy.
- Secret redaction by default.
- Export to JSON, CSV, HAR, Markdown, and HTML.
- Terminal live output with Rich.
- Local FastAPI web UI.
- Replay for safe methods by default.
- SQLite session storage.
- YAML/TOML config and `IMR_PROXY_` environment variables.
- Semantic versioning.

## Architecture

`imr_proxy/proxy/engine.py` starts mitmproxy programmatically. `imr_proxy/proxy/addons.py` captures HTTP flows, redacts secrets, stores traffic, and invokes `imr_proxy/findings/engine.py`. Data is persisted in SQLite through `imr_proxy/storage`. The web UI and exporters read the same database.

Runtime dependency note: this release requires `mitmproxy>=11.0.0`.

## Installation on Linux

```bash
git clone <repo> imr-proxy
cd imr-proxy
bash scripts/install_linux.sh
```

The Linux installer checks for Python 3.11+. If a compatible interpreter is missing, it asks before installing anything. After confirmation, it first tries the detected package manager (`apt`, `dnf`, `yum`, `pacman`, or `zypper`). If that is not available or not suitable, it can download and build Python 3.11.15 from the official python.org source release into `~/.local/imr-proxy/python-3.11.15`. It never installs Python silently. The installer resolves the project root from the script location, so it works from either the project root or the `scripts/` directory, and creates the virtual environment at `<project-root>/.venv`.

Useful installer overrides:

```bash
PYTHON_BIN=/path/to/python3.11 bash scripts/install_linux.sh
IMR_PROXY_ASSUME_YES=1 bash scripts/install_linux.sh
PYTHON_INSTALL_PREFIX="$HOME/.local/imr-proxy/python-3.11.15" bash scripts/install_linux.sh
```

Manual:

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
imr-proxy --version
```

## Installation on Windows

Recommended installer for Windows is **CMD**, not PowerShell. This avoids PowerShell `ExecutionPolicy` blocks. The project no longer ships `.ps1` installers.

```bat
git clone <repo> imr-proxy
cd imr-proxy
scripts\install_windows.cmd
```

The Windows CMD installer checks for Python 3.11+ using the Python launcher and common `python` commands. If Python 3.11+ is missing, it asks before downloading and running the official Python 3.11.9 64-bit installer from python.org. Python.org marks 3.11.9 as the last full 3.11 bugfix release with Windows binary installers; newer 3.11 security releases are source-only. The installer resolves the project root from the script location, so it works from either the project root or the `scripts\` directory, and creates the virtual environment at `<project-root>\.venv`.

Useful CMD installer options:

```bat
scripts\install_windows.cmd /PYTHON "C:\Path\To\Python311\python.exe"
scripts\install_windows.cmd /Y
scripts\install_windows.cmd /PYTHONURL "https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe"
```

The CMD installer also creates a user launcher at:

```text
%USERPROFILE%\.imr-proxy\bin\imr-proxy.cmd
```

It asks before adding that folder to your user `PATH`. After PATH is updated, open a new CMD window and run:

```bat
imr-proxy --version
```

PowerShell `.ps1` installers are intentionally not included. Use the CMD installer to avoid Windows Execution Policy blocks.

Manual CMD install:

```bat
cd C:\Path\To\imr-proxy
py -3.11 -m venv .venv
.venv\Scripts\activate.bat
python -m pip install --upgrade pip setuptools wheel
python -m pip install -e .
imr-proxy --version
```

If you previously ran version 0.1.1 from `scripts\`, it may have created `scripts\.venv`. That environment can be deleted after reinstalling with 0.1.6 because the correct environment is `<project-root>\.venv`.

## Quick start

```bash
imr-proxy start --host 127.0.0.1 --port 7413 --web --terminal
```

Browser proxy:

- HTTP proxy: `127.0.0.1:7413`
- HTTPS proxy: `127.0.0.1:7413`
- Web UI: `http://127.0.0.1:7414`

## HTTPS interception and local CA

A free public CA certificate cannot be generated for arbitrary third-party domains. The correct authorized testing workflow is:

1. Generate a local private root CA.
2. Manually install the public CA certificate into the OS/browser trust store.
3. Let mitmproxy dynamically generate per-host leaf certificates signed by that local CA.
4. Store CA private keys with safe permissions.
5. Enable HTTPS interception only with explicit user consent.
6. Use TLS passthrough when interception is disabled.
7. Optionally integrate mkcert in future versions.
8. Export/import/revoke/rotate CA material through explicit commands.
9. Never silently install certificates.

Commands:

```bash
imr-proxy ca init --ca-dir ~/.imr-proxy/ca
imr-proxy ca export --ca-dir ~/.imr-proxy/ca --format pem --output imr-proxy-ca.pem
imr-proxy ca info --ca-dir ~/.imr-proxy/ca
imr-proxy ca rotate --ca-dir ~/.imr-proxy/ca
imr-proxy start --intercept-https --cert-mode local-ca --ca-dir ~/.imr-proxy/ca --scope example.com
imr-proxy start --tls-passthrough
```

## CLI reference

```text
imr-proxy --version
imr-proxy start
imr-proxy ca init
imr-proxy ca export
imr-proxy ca rotate
imr-proxy ca info
imr-proxy config show
imr-proxy config init
imr-proxy sessions list
imr-proxy sessions export
imr-proxy report
imr-proxy replay
imr-proxy rules test
```

Important `start` flags: `--host`, `--port`, `--web`, `--no-web`, `--web-host`, `--web-port`, `--terminal`, `--quiet`, `--verbose`, `--allow-remote`, `--scope`, `--scope-file`, `--exclude`, `--exclude-file`, `--upstream-proxy`, `--proxy-auth`, `--intercept-https`, `--tls-passthrough`, `--ca-dir`, `--cert-mode local-ca|mkcert|passthrough`, `--storage`, `--session-name`, `--max-body-size`, `--capture-bodies`, `--no-capture-bodies`, `--redaction-level strict|balanced|off`, `--config`, `--no-color`, and `--jsonl`.

## Web UI

Includes dashboard, traffic table, flow detail, headers/cookies/body views, findings panel, certificate page, settings/about page, and JSON API endpoints.

## Terminal mode

```bash
imr-proxy start --terminal
imr-proxy start --terminal --jsonl
imr-proxy start --quiet
```

## Session storage and exports

SQLite stores sessions, flows, requests, responses, headers, cookies, redirect hints, findings, raw bodies when allowed, metadata, timings, version, and config snapshots.

```bash
imr-proxy sessions list
imr-proxy sessions export --session latest --format har --output traffic.har
imr-proxy sessions export --session latest --format json --output traffic.json
imr-proxy report --session latest --format html --output report.html
imr-proxy report --session latest --format md --output report.md
```

## Findings

Findings include `id`, `title`, `severity`, `confidence`, affected IDs, evidence, explanation, impact, safe validation steps, remediation, references, and false positive notes. Checks cover security headers, cookies, CORS, redirects, sensitive URL parameters, response leak indicators, and TLS metadata. Severity is intentionally conservative.

## Redaction and privacy

Default redaction is `balanced`. Strict mode masks more aggressively. Off mode must be explicit and prints a warning.

Redacted by default: Authorization, Cookie, Set-Cookie, API keys, tokens, passwords, secrets, session identifiers, JWTs, bearer/basic credentials, credit-card-like values, and optionally emails in strict mode.

## Troubleshooting

### Windows launcher still shows an old version

If `%USERPROFILE%\.imr-proxy\bin\imr-proxy.cmd` starts an older checkout, reinstall from the new project root:

```bat
cd C:\Path\To\imr-proxy
scripts\install_windows.cmd
```

The installer rewrites the user launcher so it points to the current project `.venv`. Open a new CMD or PowerShell window after PATH changes.

### mitmproxy `confdir` TypeError on startup

Version 0.1.6 fixes startup failures like `TypeError: Expected <class 'str'> for confdir, but got <class 'NoneType'>`. The proxy now omits `confdir` unless HTTPS interception/local CA mode actually needs a custom CA directory.

- TLS errors: export and manually trust the local CA in the authorized test client.
- No HTTPS body visibility: enable `--intercept-https`, use `--cert-mode local-ca`, and trust the CA.
- Remote bind refused: add `--allow-remote` intentionally and restrict network access.
- Large bodies missing: adjust `--max-body-size`.
- Sensitive data in report: use `--redaction-level strict`.

## Limitations

HTTP/3/QUIC interception is not implemented. WebSocket detail depends on mitmproxy support. TLS version/cipher metadata may be limited in passthrough mode. Findings are observations, not proof of exploitation.

## Roadmap

Rule DSL, richer request modification, mkcert helper, WebSocket live UI, OpenAPI correlation, SARIF export, Docker image, encrypted local storage option, and plugin findings packs.

## Security considerations

Keep the proxy bound to loopback by default. Install the local CA only in controlled test clients. Rotate/remove the CA after engagements. Do not disable redaction unless you are handling storage/reports securely.

## Uninstall

Remove the virtual environment and config/data directories, then manually remove the local CA from any trust store where you installed it.

## References

OWASP Secure Headers Project, OWASP ASVS, OWASP WSTG, OWASP Session Management Cheat Sheet, OWASP CORS guidance, MDN HTTP headers documentation, Mozilla TLS guidance, mitmproxy documentation, Python cryptography documentation, RFC 9110, and RFC 6265.
