"""Password hashes and persistent sessions: Python Standard Library only."""
import hashlib
import hmac
import secrets
import time
from validation import AppError, text

ROLES = ("admin", "artist", "customer")  # tuple: finite allowed roles


def hash_password(password):
    password = text(password, "รหัสผ่าน", 8, 128)
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), 120000).hex()
    return salt + ":" + digest


def verify_password(password, saved):
    try:
        salt, digest = saved.split(":")
        actual = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), 120000).hex()
        return hmac.compare_digest(actual, digest)
    except (ValueError, TypeError, AttributeError):
        return False


def token_key(token):
    return hashlib.sha256(str(token).encode()).hexdigest()


def current_user(data, token, roles=None, required=True):
    session = data["sessions"].get(token_key(token)) if token else None
    user = next((u for u in data["users"] if session and u["id"] == session["user_id"]), None)
    if not user or not user["active"] or session["expires"] <= time.time():
        if required:
            raise AppError("กรุณาเข้าสู่ระบบอีกครั้ง", 401)
        return None
    if roles and user["role"] not in roles:
        raise AppError("บัญชีนี้ไม่มีสิทธิ์ใช้งานส่วนนี้", 403)
    return user


def public_user(user):
    return {k: user[k] for k in ("id", "name", "email", "role", "active", "bio", "avatar")}


def create_session(data, user, token):
    now = int(time.time())
    data["sessions"] = {k: v for k, v in data["sessions"].items() if v["expires"] > now}
    data["sessions"][token_key(token)] = {"user_id": user["id"], "expires": now + 30 * 86400}
    return public_user(user)
