# Changelog

The format is based on Keep a Changelog, and this project follows Semantic Versioning.

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
