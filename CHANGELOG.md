# Changelog

The format is based on Keep a Changelog, and this project follows Semantic Versioning.

## [0.1.8] - 2026-07-08

### Added
- Added cyber-themed Web UI redesign with sidebar navigation, dashboard metrics, searchable traffic table, improved detail pages, and responsive styling.
- Added Web UI login portal with first-run `admin:admin` bootstrap credentials.
- Added SQLite-backed console users and server-side Web UI sessions.
- Added Web UI user creation, password reset, enable/disable actions, and authenticated API access.
- Added CLI user management commands: `users list`, `users create`, `users passwd`, `users enable`, `users disable`, and `users delete`.

### Security
- Web UI and `/api/*` routes now require authentication.
- Console passwords are stored with PBKDF2-HMAC-SHA256 and per-user random salts.
- Web sessions are stored as SHA-256 token hashes and delivered with HttpOnly `SameSite=Lax` cookies.

### Fixed
- Fixed Linux test parity by removing the pytest async plugin dependency from the mitmproxy engine regression test.
- Fixed Linux installer command exposure by creating a user launcher at `~/.local/bin/imr-proxy`.
- Fixed Web UI dashboard endpoint display so custom proxy/web ports are shown instead of hardcoded defaults.

### Changed
- Linux installer now checks that `.venv/bin/imr-proxy` exists before reporting success.
- Linux installer now warns when the launcher directory is not in `PATH` and prints the exact export command.

## [0.1.7] - 2026-07-08

### Fixed
- Fixed Web UI 500 errors on FastAPI/Starlette by using the current `TemplateResponse(request, name, context)` call style.
- Added a no-content `/favicon.ico` route to avoid noisy 404 logs in browsers.
- Added regression tests for Web UI pages and API endpoints.
- Added broader smoke tests for CLI, SQLite storage, CA lifecycle, and the mitmproxy engine wrapper with a mocked mitmproxy runtime.

### Changed
- Documented that `127.0.0.1:7413` is the forward-proxy endpoint and must be configured as browser/system proxy, while `127.0.0.1:7414` is the Web UI.
- Added clearer startup guidance so direct browsing to the proxy port is not confused with the Web UI.

## [0.1.5] - 2026-07-08

### Changed
- Changed required `mitmproxy` dependency from `>=12.0.0` to `>=11.0.0`.
- Windows installation now uses only `scripts/install_windows.cmd` as the supported installer.

### Removed
- Removed `scripts/install_windows.ps1` to avoid PowerShell Execution Policy issues.
- Removed `scripts/dev_windows.ps1`; Windows development should use the CMD installer or manual venv commands.

## [0.1.4] - 2026-07-08

### Fixed
- Fixed Windows editable installation failing with `Multiple top-level packages discovered in a flat-layout: ['configs', 'imr_proxy']`.
- Explicitly configured setuptools package discovery to include only `imr_proxy*` and exclude non-package directories.
- Updated project license metadata from the deprecated TOML table form to SPDX string `MIT`.

## [0.1.3] - 2026-07-08

### Added
- Added `scripts/install_windows.cmd` as the recommended Windows installer to avoid PowerShell Execution Policy issues.
- Added a Windows CMD user launcher at `%USERPROFILE%\.imr-proxy\bin\imr-proxy.cmd`.
- Added optional user PATH registration from the CMD installer, with confirmation before modifying PATH.

### Changed
- README now recommends CMD installation on Windows and keeps PowerShell only as optional legacy support.


## [0.1.2] - 2026-07-07

### Fixed
- Fixed Windows installer path handling when the script is executed from `scripts/`. It now resolves the project root before running `pip install -e .`.
- Fixed Linux installer path handling so the virtual environment is created at the project root instead of the current working directory.
- Installer native command failures now stop the install instead of printing a false success message.
- Development helper scripts now also resolve the project root correctly.

### Changed
- Windows installer now installs into `<project-root>\.venv` and prints both activated and direct executable commands.
- Linux installer now installs into `<project-root>/.venv` and prints both activated and direct executable commands.

## [0.1.1] - 2026-07-07

### Changed
- Updated Linux and Windows installers to detect Python 3.11+ before installation.
- When Python 3.11+ is missing, installers now ask for confirmation before downloading/installing Python.
- Linux installer can use a system package manager first or download/build Python 3.11.15 from python.org source.
- Windows installer can download and run the official Python 3.11.9 64-bit installer from python.org after user confirmation.
- Documented Python 3.11 installer behavior and non-silent installation constraints.

## [0.1.0] - 2026-07-07

### Added
- Initial defensive proxy wrapper around mitmproxy.
- CLI with start, CA, config, sessions, report, replay, and rules commands.
- Local CA generation, export, rotation, and info commands.
- SQLite storage for sessions, flows, findings, metadata, and config snapshots.
- Security findings engine for headers, cookies, CORS, redirects, URLs, TLS, and responses.
- Redaction engine with strict, balanced, and off modes.
- Web interface and report exporters.
- Linux and Windows installers.
