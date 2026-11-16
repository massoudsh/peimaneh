from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app import models, schemas
from app.auth import current_user
from app.database import get_db

router = APIRouter(prefix="/contacts", tags=["contacts"])


@router.post("", response_model=schemas.ContactOut)
def create_contact(
    payload: schemas.ContactCreate, db: Session = Depends(get_db),
    user: models.User = Depends(current_user),
):
    contact = models.Contact(**payload.model_dump())
    db.add(contact)
    db.commit()
    db.refresh(contact)
    return contact


@router.get("", response_model=list[schemas.ContactOut])
def list_contacts(
    q: str | None = Query(default=None, max_length=200),
    limit: int = Query(default=100, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    user: models.User = Depends(current_user),
):
    query = select(models.Contact).order_by(models.Contact.created_at, models.Contact.id)
    if q and q.strip():
        term = f"%{q.strip()}%"
        query = query.where(or_(
            models.Contact.name.ilike(term),
            models.Contact.company.ilike(term),
            models.Contact.country.ilike(term),
        ))
    return db.scalars(query.offset(offset).limit(limit)).all()


@router.get("/{contact_id}", response_model=schemas.ContactOut)
def get_contact(contact_id: str, db: Session = Depends(get_db), user: models.User = Depends(current_user)):
    contact = db.get(models.Contact, contact_id)
    if not contact:
        raise HTTPException(status_code=404, detail="contact not found")
    return contact
