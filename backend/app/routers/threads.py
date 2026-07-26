from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import get_db
from app.negotiation.state_machine import InvalidTransitionError, NegotiationStage, transition

router = APIRouter(prefix="/threads", tags=["threads"])


@router.post("", response_model=schemas.ThreadOut)
def create_thread(payload: schemas.ThreadCreate, db: Session = Depends(get_db)):
    contact = db.get(models.Contact, payload.contact_id)
    if not contact:
        raise HTTPException(status_code=404, detail="contact not found")
    thread = models.Thread(contact_id=payload.contact_id)
    db.add(thread)
    db.commit()
    db.refresh(thread)
    return thread


@router.get("/{thread_id}", response_model=schemas.ThreadOut)
def get_thread(thread_id: str, db: Session = Depends(get_db)):
    thread = db.get(models.Thread, thread_id)
    if not thread:
        raise HTTPException(status_code=404, detail="thread not found")
    return thread


@router.post("/{thread_id}/messages", response_model=schemas.MessageOut)
def add_message(thread_id: str, payload: schemas.MessageCreate, db: Session = Depends(get_db)):
    thread = db.get(models.Thread, thread_id)
    if not thread:
        raise HTTPException(status_code=404, detail="thread not found")

    message = models.Message(thread_id=thread_id, **payload.model_dump())
    db.add(message)
    db.commit()
    db.refresh(message)
    return message


@router.get("/{thread_id}/messages", response_model=list[schemas.MessageOut])
def list_messages(thread_id: str, db: Session = Depends(get_db)):
    thread = db.get(models.Thread, thread_id)
    if not thread:
        raise HTTPException(status_code=404, detail="thread not found")
    return thread.messages


@router.post("/{thread_id}/transition", response_model=schemas.ThreadOut)
def transition_thread(thread_id: str, target_stage: NegotiationStage, db: Session = Depends(get_db)):
    thread = db.get(models.Thread, thread_id)
    if not thread:
        raise HTTPException(status_code=404, detail="thread not found")

    try:
        thread.stage = transition(thread.stage, target_stage)
    except InvalidTransitionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    db.commit()
    db.refresh(thread)
    return thread
