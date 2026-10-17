import datetime
import hashlib
import hmac
import secrets

from fastapi import Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.database import get_db

TOKEN_DAYS = 7


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
    expires_at = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=TOKEN_DAYS)
    db.add(models.SessionToken(user_id=user.id, token_hash=hash_token(token), expires_at=expires_at))
    return token, expires_at


def current_user(
    authorization: str | None = Header(default=None), db: Session = Depends(get_db),
) -> models.User:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="authentication required")
    token = authorization[7:].strip()
    session = db.scalar(select(models.SessionToken).where(models.SessionToken.token_hash == hash_token(token)))
    now = datetime.datetime.now(datetime.timezone.utc)
    if not session or session.expires_at.replace(tzinfo=datetime.timezone.utc) <= now:
        raise HTTPException(status_code=401, detail="invalid or expired session")
    user = db.get(models.User, session.user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="inactive user")
    return user


def require_manager(user: models.User = Depends(current_user)) -> models.User:
    if user.role != models.UserRole.MANAGER:
        raise HTTPException(status_code=403, detail="manager role required")
    return user
