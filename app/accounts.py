"""Real user accounts: signup, email verification, login. Backed by SQLite (app/db.py)."""
import hashlib
import os
import re
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from app import auth
from app.db import get_conn
from app.emails import send_email

VERIFY_TOKEN_TTL = timedelta(hours=24)
APP_BASE_URL = os.environ.get("APP_BASE_URL", "http://localhost:8000")
DEMO_PASSWORD = "123456"

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class AccountError(Exception):
    pass


def validate_password(password: str) -> None:
    if len(password) < 8:
        raise AccountError("Password must be at least 8 characters")
    if not any(c.isalpha() for c in password):
        raise AccountError("Password must contain at least one letter")


def _hash_password(password: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), 200_000).hex()


def _send_verification_email(email: str, token: str) -> None:
    verify_url = f"{APP_BASE_URL}/api/auth/verify?token={token}"
    send_email(
        to=email,
        subject="Verify your VoxBox account",
        template_name="verify_email.html",
        eyebrow="VERIFY YOUR EMAIL",
        heading="Confirm it's you.",
        verify_url=verify_url,
    )


def seed_demo_users() -> None:
    """Seed the fixed demo personas as real, pre-verified accounts (password: 123456)."""
    salt = secrets.token_hex(16)
    password_hash = _hash_password(DEMO_PASSWORD, salt)
    created_at = datetime.now(timezone.utc).isoformat()
    with get_conn() as conn:
        for persona in auth.PERSONAS:
            email = f"{persona['name'].lower()}@voxbox.demo"
            conn.execute(
                """
                INSERT OR IGNORE INTO users
                    (id, email, password_hash, password_salt, email_verified, created_at)
                VALUES (?, ?, ?, ?, 1, ?)
                """,
                (persona["id"], email, password_hash, salt, created_at),
            )


def signup(email: str, password: str) -> dict:
    email = email.strip().lower()
    if not EMAIL_RE.match(email):
        raise AccountError("Invalid email address")
    validate_password(password)

    salt = secrets.token_hex(16)
    password_hash = _hash_password(password, salt)
    user_id = str(uuid.uuid4())
    token = secrets.token_urlsafe(32)
    expires_at = (datetime.now(timezone.utc) + VERIFY_TOKEN_TTL).isoformat()
    created_at = datetime.now(timezone.utc).isoformat()

    with get_conn() as conn:
        existing = conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
        if existing is not None:
            raise AccountError("An account with this email already exists")
        conn.execute(
            """
            INSERT INTO users (id, email, password_hash, password_salt, email_verified,
                                verify_token, verify_token_expires_at, created_at)
            VALUES (?, ?, ?, ?, 0, ?, ?, ?)
            """,
            (user_id, email, password_hash, salt, token, expires_at, created_at),
        )

    _send_verification_email(email, token)
    return {"id": user_id, "email": email}


def verify_email(token: str) -> bool:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT id, verify_token_expires_at FROM users WHERE verify_token = ?", (token,)
        ).fetchone()
        if row is None:
            return False
        if datetime.fromisoformat(row["verify_token_expires_at"]) < datetime.now(timezone.utc):
            return False
        conn.execute(
            "UPDATE users SET email_verified = 1, verify_token = NULL WHERE id = ?",
            (row["id"],),
        )
        return True


def login(email: str, password: str) -> dict:
    email = email.strip().lower()
    with get_conn() as conn:
        row = conn.execute(
            "SELECT id, email, password_hash, password_salt, email_verified FROM users WHERE email = ?",
            (email,),
        ).fetchone()
    if row is None:
        raise AccountError("Invalid email or password")
    if _hash_password(password, row["password_salt"]) != row["password_hash"]:
        raise AccountError("Invalid email or password")
    if not row["email_verified"]:
        raise AccountError("Please verify your email before logging in")
    user = {"id": row["id"], "email": row["email"]}
    persona = auth.persona_for_id(row["id"])
    if persona is not None:
        user["name"] = persona["name"]
        user["role"] = persona["role"]
    return user
