from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import models, schemas
from app.auth import hash_password, issue_token, verify_password, current_user
from app.database import get_db

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=schemas.AuthResponse, status_code=201)
def register(payload: schemas.AuthRegister, db: Session = Depends(get_db)):
    email = payload.email.strip().lower()
    if db.scalar(select(models.User).where(models.User.email == email)):
        raise HTTPException(status_code=409, detail="email already registered")
    user_count = db.scalar(select(func.count()).select_from(models.User))
    requested_role = models.UserRole.MANAGER if user_count == 0 else models.UserRole.SALES
    if payload.role != requested_role.value:
        raise HTTPException(status_code=403, detail="the first account must be manager; later accounts are sales users")
    user = models.User(email=email, password_hash=hash_password(payload.password), role=requested_role)
    db.add(user)
    db.flush()
    token, expires_at = issue_token(db, user)
    db.commit()
    return schemas.AuthResponse(access_token=token, expires_at=expires_at)


@router.post("/login", response_model=schemas.AuthResponse)
def login(payload: schemas.AuthLogin, db: Session = Depends(get_db)):
    user = db.scalar(select(models.User).where(models.User.email == payload.email.strip().lower()))
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="invalid email or password")
    token, expires_at = issue_token(db, user)
    db.commit()
    return schemas.AuthResponse(access_token=token, expires_at=expires_at)


@router.get("/me", response_model=schemas.UserOut)
def me(user: models.User = Depends(current_user)):
    return user
