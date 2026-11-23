import binascii
import hashlib
import os
import secrets
from datetime import datetime, timedelta

import config

PBKDF2_ITERATIONS = 200_000


def hash_password(password: str, salt: str = None) -> tuple[str, str]:
    salt = salt or secrets.token_hex(16)
    derived = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt.encode("utf-8"), PBKDF2_ITERATIONS
    )
    return binascii.hexlify(derived).decode("utf-8"), salt


def verify_password(password: str, salt: str, expected_hash: str) -> bool:
    candidate, _ = hash_password(password, salt)
    return secrets.compare_digest(candidate, expected_hash)


def create_user(conn, email: str, name: str, password: str) -> int:
    password_hash, salt = hash_password(password)
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO users (email, name, password_hash, salt) VALUES (%s, %s, %s, %s)",
            (email.strip().lower(), name.strip(), password_hash, salt),
        )
        return cur.lastrowid


def authenticate(conn, email: str, password: str):
    with conn.cursor() as cur:
        cur.execute("SELECT * FROM users WHERE email = %s", (email.strip().lower(),))
        user = cur.fetchone()
    if not user:
        return None
    if not verify_password(password, user["salt"], user["password_hash"]):
        return None
    return user


def create_session(conn, user_id: int) -> str:
    token = secrets.token_hex(32)
    expires_at = datetime.utcnow() + timedelta(hours=config.SESSION_LIFETIME_HOURS)
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO sessions (token, user_id, expires_at) VALUES (%s, %s, %s)",
            (token, user_id, expires_at),
        )
    return token


def get_user_for_token(conn, token: str):
    if not token:
        return None
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT u.* FROM sessions s
            JOIN users u ON u.id = s.user_id
            WHERE s.token = %s AND s.expires_at > UTC_TIMESTAMP()
            """,
            (token,),
        )
        return cur.fetchone()


def destroy_session(conn, token: str):
    with conn.cursor() as cur:
        cur.execute("DELETE FROM sessions WHERE token = %s", (token,))


PASSWORD_RESET_LIFETIME_HOURS = 1


def create_password_reset(conn, user_id: int) -> str:
    """One-time, time-limited token for the forgot-password flow. Also
    used to claim a passwordless account (ANU Sport sync / "+ add guest"),
    since setting a password via a valid token works the same either way."""
    token = secrets.token_hex(32)
    expires_at = datetime.utcnow() + timedelta(hours=PASSWORD_RESET_LIFETIME_HOURS)
    with conn.cursor() as cur:
        cur.execute("DELETE FROM password_resets WHERE user_id = %s", (user_id,))
        cur.execute(
            "INSERT INTO password_resets (token, user_id, expires_at) VALUES (%s, %s, %s)",
            (token, user_id, expires_at),
        )
    return token


def get_user_for_reset_token(conn, token: str):
    if not token:
        return None
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT u.* FROM password_resets r
            JOIN users u ON u.id = r.user_id
            WHERE r.token = %s AND r.expires_at > UTC_TIMESTAMP()
            """,
            (token,),
        )
        return cur.fetchone()


def consume_password_reset(conn, token: str, new_password: str) -> None:
    """Sets the account's password and deletes the (now used) token."""
    user = get_user_for_reset_token(conn, token)
    if not user:
        return
    password_hash, salt = hash_password(new_password)
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE users SET password_hash = %s, salt = %s WHERE id = %s",
            (password_hash, salt, user["id"]),
        )
        cur.execute("DELETE FROM password_resets WHERE token = %s", (token,))
