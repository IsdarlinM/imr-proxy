#!/usr/bin/env bash
set -euo pipefail

REQUIRED_MAJOR=3
REQUIRED_MINOR=11
PYTHON_SOURCE_VERSION="${PYTHON_SOURCE_VERSION:-3.11.15}"
PYTHON_SOURCE_URL="${PYTHON_SOURCE_URL:-https://www.python.org/ftp/python/${PYTHON_SOURCE_VERSION}/Python-${PYTHON_SOURCE_VERSION}.tar.xz}"
PYTHON_INSTALL_PREFIX="${PYTHON_INSTALL_PREFIX:-$HOME/.local/imr-proxy/python-${PYTHON_SOURCE_VERSION}}"
ASSUME_YES="${IMR_PROXY_ASSUME_YES:-0}"
PYTHON_BIN="${PYTHON_BIN:-}"
USER_BIN="${IMR_PROXY_USER_BIN:-$HOME/.local/bin}"
DETECTED_PYTHON=""
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
VENV_DIR="$PROJECT_ROOT/.venv"
COMMAND_PATH="$VENV_DIR/bin/imr-proxy"
LAUNCHER_PATH="$USER_BIN/imr-proxy"

log() { printf '[*] %s\n' "$*" >&2; }
warn() { printf '[!] %s\n' "$*" >&2; }
fail() { printf '[x] %s\n' "$*" >&2; exit 1; }

confirm() {
    local prompt="$1"
    if [[ "$ASSUME_YES" == "1" ]]; then
        return 0
    fi
    local reply
    read -r -p "$prompt [y/N]: " reply
    case "$reply" in
        y|Y|yes|YES|Yes) return 0 ;;
        *) return 1 ;;
    esac
}

is_python_compatible() {
    local candidate="$1"
    "$candidate" - <<'PY' >/dev/null 2>&1
import sys
raise SystemExit(0 if sys.version_info >= (3, 11) else 1)
PY
}

find_python() {
    local candidates=()
    if [[ -n "$PYTHON_BIN" ]]; then
        candidates+=("$PYTHON_BIN")
    fi
    candidates+=(python3.13 python3.12 python3.11 python3 python)

    local candidate resolved
    for candidate in "${candidates[@]}"; do
        if resolved="$(command -v "$candidate" 2>/dev/null)" && is_python_compatible "$resolved"; then
            printf '%s\n' "$resolved"
            return 0
        fi
    done
    return 1
}

try_install_with_package_manager() {
    if ! confirm "Try to install Python 3.11+ using the detected system package manager first?"; then
        return 1
    fi

    if command -v apt-get >/dev/null 2>&1; then
        log "Detected apt-get. Installing python3.11, venv and build dependencies."
        sudo apt-get update
        sudo apt-get install -y python3.11 python3.11-venv python3.11-dev build-essential libssl-dev zlib1g-dev libbz2-dev libreadline-dev libsqlite3-dev libffi-dev liblzma-dev tk-dev uuid-dev xz-utils curl ca-certificates
        return 0
    fi

    if command -v dnf >/dev/null 2>&1; then
        log "Detected dnf. Installing Python 3.11 packages when available."
        sudo dnf install -y python3.11 python3.11-devel python3.11-pip gcc make openssl-devel bzip2-devel libffi-devel zlib-devel readline-devel sqlite-devel xz-devel tk-devel uuid-devel curl ca-certificates
        return 0
    fi

    if command -v yum >/dev/null 2>&1; then
        log "Detected yum. Installing Python 3.11 packages when available."
        sudo yum install -y python3.11 python3.11-devel python3.11-pip gcc make openssl-devel bzip2-devel libffi-devel zlib-devel readline-devel sqlite-devel xz-devel tk-devel uuid-devel curl ca-certificates
        return 0
    fi

    if command -v pacman >/dev/null 2>&1; then
        log "Detected pacman. Installing Python and build dependencies."
        sudo pacman -Sy --needed python python-pip base-devel openssl zlib bzip2 readline sqlite xz tk libffi curl ca-certificates
        return 0
    fi

    if command -v zypper >/dev/null 2>&1; then
        log "Detected zypper. Installing Python and build dependencies."
        sudo zypper install -y python311 python311-devel python311-pip gcc make libopenssl-devel zlib-devel libbz2-devel readline-devel sqlite3-devel xz-devel tk-devel libffi-devel curl ca-certificates
        return 0
    fi

    warn "No supported package manager detected."
    return 1
}

require_build_tools() {
    local missing=()
    command -v curl >/dev/null 2>&1 || command -v wget >/dev/null 2>&1 || missing+=(curl-or-wget)
    command -v tar >/dev/null 2>&1 || missing+=(tar)
    command -v make >/dev/null 2>&1 || missing+=(make)
    command -v gcc >/dev/null 2>&1 || command -v cc >/dev/null 2>&1 || missing+=(gcc-or-cc)

    if (( ${#missing[@]} > 0 )); then
        warn "Missing build tools: ${missing[*]}"
        warn "Install compiler/build dependencies, then run this installer again."
        return 1
    fi
    return 0
}

install_from_python_org_source() {
    if ! confirm "Download and build Python ${PYTHON_SOURCE_VERSION} from python.org into ${PYTHON_INSTALL_PREFIX}?"; then
        return 1
    fi

    require_build_tools || return 1

    local build_root archive src_dir jobs
    build_root="$(mktemp -d)"
    archive="$build_root/Python-${PYTHON_SOURCE_VERSION}.tar.xz"
    src_dir="$build_root/Python-${PYTHON_SOURCE_VERSION}"
    jobs="$(getconf _NPROCESSORS_ONLN 2>/dev/null || printf '2')"

    log "Downloading ${PYTHON_SOURCE_URL}"
    if command -v curl >/dev/null 2>&1; then
        curl -fL --proto '=https' --tlsv1.2 -o "$archive" "$PYTHON_SOURCE_URL"
    else
        wget -O "$archive" "$PYTHON_SOURCE_URL"
    fi

    log "Extracting Python source"
    tar -xf "$archive" -C "$build_root"

    log "Building Python ${PYTHON_SOURCE_VERSION}. This may require OpenSSL/zlib/sqlite development headers."
    (
        cd "$src_dir"
        ./configure --prefix="$PYTHON_INSTALL_PREFIX" --enable-optimizations --with-ensurepip=install
        make -j"$jobs"
        make install
    )

    rm -rf "$build_root"
    export PYTHON_BIN="$PYTHON_INSTALL_PREFIX/bin/python3.11"
    [[ -x "$PYTHON_BIN" ]] || fail "Python build finished, but ${PYTHON_BIN} was not found."
    log "Installed local Python: $PYTHON_BIN"
}

ensure_python() {
    local found
    if found="$(find_python)"; then
        DETECTED_PYTHON="$found"
        return 0
    fi

    warn "Python 3.11+ was not found. imr-proxy requires Python 3.11 or newer."
    if ! confirm "Do you want this installer to download/install Python 3.11+ now?"; then
        fail "Install Python 3.11+ manually, or rerun with IMR_PROXY_ASSUME_YES=1 to allow automated installation."
    fi

    try_install_with_package_manager || install_from_python_org_source || fail "Could not install Python 3.11+."

    if found="$(find_python)"; then
        DETECTED_PYTHON="$found"
        return 0
    fi

    fail "Python 3.11+ still was not found after installation. Open a new shell or set PYTHON_BIN explicitly."
}

create_launcher() {
    mkdir -p "$USER_BIN"
    cat > "$LAUNCHER_PATH" <<EOF
#!/usr/bin/env sh
exec "$COMMAND_PATH" "\$@"
EOF
    chmod 0755 "$LAUNCHER_PATH"
    log "Global launcher created at: $LAUNCHER_PATH"

    case ":$PATH:" in
        *":$USER_BIN:"*)
            return 0
            ;;
    esac

    warn "$USER_BIN is not currently in PATH."
    warn "You can run imr-proxy directly with: '$LAUNCHER_PATH' --version"
    warn "To make it available in future shells, add this line to ~/.profile, ~/.bashrc, or ~/.zshrc:"
    warn "export PATH=\"$USER_BIN:\$PATH\""
}

main() {
    log "Installing imr-proxy"
    log "Project root: $PROJECT_ROOT"
    [[ -f "$PROJECT_ROOT/pyproject.toml" ]] || fail "pyproject.toml was not found at $PROJECT_ROOT. Keep scripts/ inside the project root."

    if [[ -d "$SCRIPT_DIR/.venv" ]]; then
        warn "A previous virtual environment exists inside scripts/.venv. It is not used anymore. You can delete it after this install succeeds: $SCRIPT_DIR/.venv"
    fi

    ensure_python
    local python_cmd="$DETECTED_PYTHON"
    log "Using Python: $python_cmd ($($python_cmd --version))"

    "$python_cmd" -m venv "$VENV_DIR"
    "$VENV_DIR/bin/python" -m pip install --upgrade pip setuptools wheel
    (
        cd "$PROJECT_ROOT"
        "$VENV_DIR/bin/python" -m pip install -e .
    )

    [[ -x "$COMMAND_PATH" ]] || fail "Installation finished but command was not created at $COMMAND_PATH"
    create_launcher

    log "Installed successfully."
    log "Activate it with: cd '$PROJECT_ROOT' && source .venv/bin/activate"
    log "Check version with: imr-proxy --version"
    log "Direct command without activation: '$COMMAND_PATH' --version"
}

main "$@"
