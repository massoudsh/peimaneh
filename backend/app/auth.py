import datetime
import hashlib
import hmac
import os
import secrets

from fastapi import Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.database import get_db

TOKEN_DAYS = 7
MAX_FAILED_LOGINS = 5
LOCK_MINUTES = 15


def _now() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


def _utc(value: datetime.datetime) -> datetime.datetime:
    return value if value.tzinfo else value.replace(tzinfo=datetime.timezone.utc)


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 310_000)
    return f"{salt.hex()}${digest.hex()}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        salt_hex, digest_hex = encoded.split("$", 1)
        digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt_hex), 310_000)
        return hmac.compare_digest(digest.hex(), digest_hex)
    except (ValueError, TypeError):
        return False


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def issue_token(db: Session, user: models.User) -> tuple[str, datetime.datetime]:
    token = secrets.token_urlsafe(32)
    expires_at = _now() + datetime.timedelta(days=TOKEN_DAYS)
    db.add(models.SessionToken(user_id=user.id, token_hash=hash_token(token), expires_at=expires_at))
    return token, expires_at


def revoke_all_sessions(db: Session, user_id: str) -> None:
    for session in db.scalars(select(models.SessionToken).where(models.SessionToken.user_id == user_id)):
        db.delete(session)


def _bearer_token(authorization: str | None) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="authentication required")
    token = authorization[7:].strip()
    if not token:
        raise HTTPException(status_code=401, detail="authentication required")
    return token


def current_identity(
    authorization: str | None = Header(default=None), db: Session = Depends(get_db),
) -> tuple[models.User, models.SessionToken]:
    session = db.scalar(
        select(models.SessionToken).where(
            models.SessionToken.token_hash == hash_token(_bearer_token(authorization))
        )
    )
    if not session or _utc(session.expires_at) <= _now():
        raise HTTPException(status_code=401, detail="invalid or expired session")
    user = db.get(models.User, session.user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="inactive user")
    return user, session


def current_user(identity: tuple[models.User, models.SessionToken] = Depends(current_identity)) -> models.User:
    return identity[0]


def require_manager(user: models.User = Depends(current_user)) -> models.User:
    if user.role != models.UserRole.MANAGER:
        raise HTTPException(status_code=403, detail="manager role required")
    return user


def bootstrap_allowed() -> bool:
    """ساخت نخستین حساب فقط وقتی مجاز است که صریحاً برای راه‌اندازی فعال شود."""
    return os.getenv("ALLOW_BOOTSTRAP_REGISTRATION", "false").lower() in {"1", "true", "yes"}


def lock_state(user: models.User) -> None:
    """قفل ورود موقت پس از تلاش‌های ناموفق متوالی را اعمال می‌کند."""
    if user.locked_until and _utc(user.locked_until) > _now():
        raise HTTPException(status_code=423, detail="account temporarily locked")