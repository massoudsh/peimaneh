import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import models, schemas
from app.auth import (
    LOCK_MINUTES,
    MAX_FAILED_LOGINS,
    bootstrap_allowed,
    current_identity,
    current_user,
    hash_password,
    issue_token,
    lock_state,
    require_manager,
    revoke_all_sessions,
    verify_password,
)
from app.database import get_db

router = APIRouter(prefix="/auth", tags=["auth"])


def _email(value: str) -> str:
    return value.strip().lower()


@router.post("/bootstrap", response_model=schemas.AuthResponse, status_code=201)
def bootstrap(payload: schemas.AuthBootstrap, db: Session = Depends(get_db)):
    """نخستین حساب فقط با فعال‌سازی صریح bootstrap و وقتی هیچ کاربری وجود ندارد."""
    if not bootstrap_allowed():
        raise HTTPException(status_code=404, detail="not found")
    if db.scalar(select(func.count()).select_from(models.User)):
        raise HTTPException(status_code=409, detail="workspace already initialized")
    user = models.User(
        email=_email(payload.email), password_hash=hash_password(payload.password),
        role=models.UserRole.MANAGER,
    )
    db.add(user)
    db.flush()
    token, expires_at = issue_token(db, user)
    db.commit()
    return schemas.AuthResponse(access_token=token, expires_at=expires_at)


@router.post("/login", response_model=schemas.AuthResponse)
def login(payload: schemas.AuthLogin, db: Session = Depends(get_db)):
    user = db.scalar(select(models.User).where(models.User.email == _email(payload.email)))
    if not user:
        raise HTTPException(status_code=401, detail="invalid email or password")
    lock_state(user)
    if not verify_password(payload.password, user.password_hash):
        user.failed_login_attempts = (user.failed_login_attempts or 0) + 1
        if user.failed_login_attempts >= MAX_FAILED_LOGINS:
            user.locked_until = models._now() + datetime.timedelta(minutes=LOCK_MINUTES)
            user.failed_login_attempts = 0
        db.commit()
        raise HTTPException(status_code=401, detail="invalid email or password")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="account disabled")
    user.failed_login_attempts = 0
    user.locked_until = None
    token, expires_at = issue_token(db, user)
    db.commit()
    return schemas.AuthResponse(access_token=token, expires_at=expires_at)


@router.post("/logout", status_code=204)
def logout(
    identity: tuple[models.User, models.SessionToken] = Depends(current_identity),
    db: Session = Depends(get_db),
):
    db.delete(identity[1])
    db.commit()


@router.post("/logout-all", status_code=204)
def logout_all(user: models.User = Depends(current_user), db: Session = Depends(get_db)):
    revoke_all_sessions(db, user.id)
    db.commit()


@router.get("/me", response_model=schemas.UserOut)
def me(user: models.User = Depends(current_user)):
    return user


@router.get("/users", response_model=list[schemas.UserOut])
def list_users(user: models.User = Depends(require_manager), db: Session = Depends(get_db)):
    return db.scalars(select(models.User).order_by(models.User.created_at)).all()


@router.post("/users", response_model=schemas.UserOut, status_code=201)
def create_user(
    payload: schemas.UserCreate, manager: models.User = Depends(require_manager),
    db: Session = Depends(get_db),
):
    email = _email(payload.email)
    if db.scalar(select(models.User).where(models.User.email == email)):
        raise HTTPException(status_code=409, detail="email already registered")
    user = models.User(
        email=email, password_hash=hash_password(payload.password),
        role=models.UserRole(payload.role),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.patch("/users/{user_id}", response_model=schemas.UserOut)
def update_user(
    user_id: str, payload: schemas.UserUpdate,
    manager: models.User = Depends(require_manager), db: Session = Depends(get_db),
):
    user = db.get(models.User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="user not found")
    if user.id == manager.id and payload.is_active is False:
        raise HTTPException(status_code=409, detail="cannot deactivate your own account")
    if user.id == manager.id and payload.role == models.UserRole.SALES:
        raise HTTPException(status_code=409, detail="cannot remove your own manager role")
    if payload.is_active is not None:
        user.is_active = payload.is_active
        if not payload.is_active:
            revoke_all_sessions(db, user.id)
    if payload.role is not None:
        user.role = models.UserRole(payload.role)
        revoke_all_sessions(db, user.id)
    db.commit()
    db.refresh(user)
    return user
