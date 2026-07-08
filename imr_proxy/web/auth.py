from __future__ import annotations

import base64
import hashlib
import hmac
import re
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Any

PASSWORD_SCHEME = "pbkdf2_sha256"
PASSWORD_ITERATIONS = 260_000
SESSION_COOKIE = "imr_proxy_session"
SESSION_TTL_HOURS = 12
_USERNAME_RE = re.compile(r"^[a-zA-Z0-9_.@-]{3,64}$")


class AuthError(ValueError):
    pass


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _unb64(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


def hash_password(password: str, *, iterations: int = PASSWORD_ITERATIONS) -> str:
    if len(password) < 5:
        raise AuthError("Password must be at least 5 characters long.")
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return f"{PASSWORD_SCHEME}${iterations}${_b64(salt)}${_b64(digest)}"


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        scheme, iterations_raw, salt_raw, digest_raw = stored_hash.split("$", 3)
        if scheme != PASSWORD_SCHEME:
            return False
        iterations = int(iterations_raw)
        salt = _unb64(salt_raw)
        expected = _unb64(digest_raw)
        candidate = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
        return hmac.compare_digest(candidate, expected)
    except Exception:
        return False


def validate_username(username: str) -> str:
    normalized = username.strip().lower()
    if not _USERNAME_RE.fullmatch(normalized):
        raise AuthError("Username must be 3-64 chars: letters, digits, dot, underscore, dash, or @.")
    return normalized


class UserRepository:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def ensure_default_admin(self) -> None:
        row = self.conn.execute("SELECT COUNT(*) AS n FROM users").fetchone()
        if row and row["n"]:
            return
        self.create_user("admin", "admin", is_admin=True, must_change_password=True)

    def create_user(
        self,
        username: str,
        password: str,
        *,
        is_admin: bool = False,
        must_change_password: bool = False,
        created_by: str | None = None,
    ) -> dict[str, Any]:
        normalized = validate_username(username)
        now = utc_now().isoformat()
        password_hash = hash_password(password)
        try:
            self.conn.execute(
                """
                INSERT INTO users(username,password_hash,is_admin,is_active,must_change_password,created_at,updated_at,created_by)
                VALUES(?,?,?,?,?,?,?,?)
                """,
                (normalized, password_hash, int(is_admin), 1, int(must_change_password), now, now, created_by),
            )
            self.conn.commit()
        except sqlite3.IntegrityError as exc:
            raise AuthError(f"User already exists: {normalized}") from exc
        return self.get_user(normalized) or {"username": normalized}

    def get_user(self, username: str) -> dict[str, Any] | None:
        normalized = validate_username(username)
        row = self.conn.execute(
            "SELECT username,is_admin,is_active,must_change_password,created_at,updated_at,last_login_at,created_by FROM users WHERE username=?",
            (normalized,),
        ).fetchone()
        return dict(row) if row else None

    def get_user_with_hash(self, username: str) -> dict[str, Any] | None:
        normalized = validate_username(username)
        row = self.conn.execute("SELECT * FROM users WHERE username=?", (normalized,)).fetchone()
        return dict(row) if row else None

    def list_users(self) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            """
            SELECT username,is_admin,is_active,must_change_password,created_at,updated_at,last_login_at,created_by
            FROM users ORDER BY username ASC
            """
        ).fetchall()
        return [dict(row) for row in rows]

    def authenticate(self, username: str, password: str) -> dict[str, Any] | None:
        try:
            user = self.get_user_with_hash(username)
        except AuthError:
            return None
        if not user or not user["is_active"]:
            return None
        if not verify_password(password, user["password_hash"]):
            return None
        now = utc_now().isoformat()
        self.conn.execute("UPDATE users SET last_login_at=?, updated_at=? WHERE username=?", (now, now, user["username"]))
        self.conn.commit()
        user.pop("password_hash", None)
        return user

    def set_password(self, username: str, password: str, *, must_change_password: bool = False) -> None:
        normalized = validate_username(username)
        user = self.get_user(normalized)
        if not user:
            raise AuthError(f"User not found: {normalized}")
        now = utc_now().isoformat()
        self.conn.execute(
            "UPDATE users SET password_hash=?, must_change_password=?, updated_at=? WHERE username=?",
            (hash_password(password), int(must_change_password), now, normalized),
        )
        self.conn.commit()

    def set_active(self, username: str, active: bool) -> None:
        normalized = validate_username(username)
        if normalized == "admin" and not active:
            raise AuthError("The default admin user cannot be disabled from this command.")
        now = utc_now().isoformat()
        cur = self.conn.execute("UPDATE users SET is_active=?, updated_at=? WHERE username=?", (int(active), now, normalized))
        self.conn.commit()
        if cur.rowcount == 0:
            raise AuthError(f"User not found: {normalized}")

    def delete_user(self, username: str) -> None:
        normalized = validate_username(username)
        if normalized == "admin":
            raise AuthError("The default admin user cannot be deleted from this command.")
        cur = self.conn.execute("DELETE FROM users WHERE username=?", (normalized,))
        self.conn.commit()
        if cur.rowcount == 0:
            raise AuthError(f"User not found: {normalized}")

    def create_session(self, username: str, *, user_agent: str | None = None, ip_address: str | None = None) -> tuple[str, str]:
        normalized = validate_username(username)
        token = secrets.token_urlsafe(32)
        csrf_token = secrets.token_urlsafe(24)
        token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
        now = utc_now()
        expires_at = now + timedelta(hours=SESSION_TTL_HOURS)
        self.conn.execute(
            """
            INSERT INTO web_sessions(token_hash,username,csrf_token,created_at,expires_at,last_seen_at,user_agent,ip_address)
            VALUES(?,?,?,?,?,?,?,?)
            """,
            (
                token_hash,
                normalized,
                csrf_token,
                now.isoformat(),
                expires_at.isoformat(),
                now.isoformat(),
                user_agent,
                ip_address,
            ),
        )
        self.conn.commit()
        return token, csrf_token

    def get_session_user(self, token: str | None) -> dict[str, Any] | None:
        if not token:
            return None
        token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
        row = self.conn.execute(
            """
            SELECT s.username,s.csrf_token,s.expires_at,u.is_admin,u.is_active,u.must_change_password,u.last_login_at
            FROM web_sessions s JOIN users u ON u.username=s.username
            WHERE s.token_hash=?
            """,
            (token_hash,),
        ).fetchone()
        if not row:
            return None
        data = dict(row)
        if not data["is_active"]:
            self.delete_session(token)
            return None
        try:
            expires_at = datetime.fromisoformat(data["expires_at"])
        except ValueError:
            self.delete_session(token)
            return None
        if expires_at <= utc_now():
            self.delete_session(token)
            return None
        self.conn.execute("UPDATE web_sessions SET last_seen_at=? WHERE token_hash=?", (utc_now().isoformat(), token_hash))
        self.conn.commit()
        return data

    def delete_session(self, token: str | None) -> None:
        if not token:
            return
        token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
        self.conn.execute("DELETE FROM web_sessions WHERE token_hash=?", (token_hash,))
        self.conn.commit()

    def purge_expired_sessions(self) -> int:
        cur = self.conn.execute("DELETE FROM web_sessions WHERE expires_at <= ?", (utc_now().isoformat(),))
        self.conn.commit()
        return cur.rowcount
