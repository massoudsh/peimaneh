import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app import models, schemas
from app.auth import current_user
from app.database import get_db
from app.negotiation.state_machine import (
    ALLOWED_TRANSITIONS,
    InvalidTransitionError,
    NegotiationStage,
    transition,
)

router = APIRouter(prefix="/threads", tags=["threads"])


def _thread(thread_id: str, db: Session) -> models.Thread:
    thread = db.get(models.Thread, thread_id)
    if not thread:
        raise HTTPException(status_code=404, detail="thread not found")
    return thread


def _audit(db: Session, thread_id: str, actor: str, action: str, detail: dict) -> None:
    db.add(models.AuditLog(thread_id=thread_id, actor=actor, action=action, detail=detail))


@router.post("", response_model=schemas.ThreadOut)
def create_thread(
    payload: schemas.ThreadCreate, db: Session = Depends(get_db),
    user: models.User = Depends(current_user),
):
    contact = db.get(models.Contact, payload.contact_id)
    if not contact:
        raise HTTPException(status_code=404, detail="contact not found")
    thread = models.Thread(contact_id=payload.contact_id)
    db.add(thread)
    db.flush()
    _audit(db, thread.id, user.email, "thread_created", {"contact_id": contact.id})
    db.commit()
    db.refresh(thread)
    return thread


@router.get("", response_model=list[schemas.ThreadOut])
def list_threads(
    stage: NegotiationStage | None = None,
    contact_id: str | None = None,
    open_only: bool = False,
    due_only: bool = False,
    q: str | None = Query(default=None, max_length=200),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    user: models.User = Depends(current_user),
):
    query = select(models.Thread)
    if q and q.strip():
        term = f"%{q.strip()}%"
        query = query.join(models.Contact).where(
            or_(
                models.Contact.name.ilike(term),
                models.Contact.company.ilike(term),
                models.Thread.summary.ilike(term),
            )
        )
    if stage is not None:
        query = query.where(models.Thread.stage == stage)
    if contact_id is not None:
        query = query.where(models.Thread.contact_id == contact_id)
    if open_only or due_only:
        query = query.where(models.Thread.stage != NegotiationStage.CONFIRMATION)
    if due_only:
        query = query.where(models.Thread.next_follow_up_at <= models._now())
        query = query.order_by(models.Thread.next_follow_up_at, models.Thread.id)
    else:
        query = query.order_by(models.Thread.updated_at.desc(), models.Thread.id)
    return db.scalars(query.offset(offset).limit(limit)).all()


@router.get("/{thread_id}", response_model=schemas.ThreadOut)
def get_thread(thread_id: str, db: Session = Depends(get_db), user: models.User = Depends(current_user)):
    return _thread(thread_id, db)


@router.get("/{thread_id}/transitions", response_model=schemas.StageTransitionsOut)
def list_transitions(
    thread_id: str, db: Session = Depends(get_db), user: models.User = Depends(current_user),
):
    thread = _thread(thread_id, db)
    allowed = sorted(ALLOWED_TRANSITIONS[thread.stage] - {thread.stage}, key=lambda stage: list(NegotiationStage).index(stage))
    return schemas.StageTransitionsOut(
        current_stage=thread.stage,
        allowed_stages=allowed,
        requires_manager=NegotiationStage.CONFIRMATION in allowed,
    )


@router.post("/{thread_id}/messages", response_model=schemas.MessageOut)
def add_message(
    thread_id: str, payload: schemas.MessageCreate, db: Session = Depends(get_db),
    user: models.User = Depends(current_user),
):
    thread = _thread(thread_id, db)
    status = {
        models.MessageSender.CONTACT: models.MessageStatus.RECEIVED,
        models.MessageSender.HUMAN: models.MessageStatus.SENT,
        models.MessageSender.AGENT_DRAFT: models.MessageStatus.NEEDS_APPROVAL,
    }[payload.sender]
    message = models.Message(thread_id=thread_id, status=status, **payload.model_dump())
    thread.updated_at = models._now()
    if payload.sender == models.MessageSender.CONTACT and thread.next_follow_up_at is not None:
        thread.next_follow_up_at = None
        _audit(db, thread_id, "system", "follow_up_cancelled", {"reason": "contact_replied"})
    db.add(message)
    db.commit()
    db.refresh(message)
    return message


@router.get("/{thread_id}/messages", response_model=list[schemas.MessageOut])
def list_messages(
    thread_id: str,
    limit: int = Query(default=200, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    user: models.User = Depends(current_user),
):
    _thread(thread_id, db)
    return db.scalars(
        select(models.Message).where(models.Message.thread_id == thread_id)
        .order_by(models.Message.created_at, models.Message.id).offset(offset).limit(limit)
    ).all()


@router.post("/{thread_id}/transition", response_model=schemas.ThreadOut)
def transition_thread(
    thread_id: str, payload: schemas.StageTransitionRequest,
    db: Session = Depends(get_db), user: models.User = Depends(current_user),
):
    thread = _thread(thread_id, db)
    target = payload.target_stage
    if target == NegotiationStage.CONFIRMATION and user.role != models.UserRole.MANAGER:
        raise HTTPException(status_code=403, detail="only a manager can confirm an opportunity")
    previous = thread.stage
    try:
        thread.stage = transition(thread.stage, target)
    except InvalidTransitionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if target == NegotiationStage.CONFIRMATION:
        thread.next_follow_up_at = None
    _audit(
        db, thread_id, user.email, "stage_transition",
        {"from": previous.value, "to": target.value},
    )
    db.commit()
    db.refresh(thread)
    return thread


@router.put("/{thread_id}/follow-up", response_model=schemas.ThreadOut)
def schedule_follow_up(
    thread_id: str, payload: schemas.FollowUpSchedule, db: Session = Depends(get_db),
    user: models.User = Depends(current_user),
):
    thread = _thread(thread_id, db)
    if thread.stage == NegotiationStage.CONFIRMATION:
        raise HTTPException(status_code=409, detail="confirmed threads cannot be scheduled")
    due_at = payload.due_at.astimezone(datetime.timezone.utc)
    if due_at <= models._now():
        raise HTTPException(status_code=422, detail="due_at must be in the future")
    thread.next_follow_up_at = due_at
    _audit(db, thread_id, user.email, "follow_up_scheduled", {"due_at": due_at.isoformat()})
    db.commit()
    db.refresh(thread)
    return thread


@router.delete("/{thread_id}/follow-up", response_model=schemas.ThreadOut)
def cancel_follow_up(
    thread_id: str, db: Session = Depends(get_db), user: models.User = Depends(current_user),
):
    thread = _thread(thread_id, db)
    if thread.next_follow_up_at is not None:
        thread.next_follow_up_at = None
        _audit(db, thread_id, user.email, "follow_up_cancelled", {})
        db.commit()
        db.refresh(thread)
    return thread


@router.post("/{thread_id}/follow-up/complete", response_model=schemas.ThreadOut)
def complete_follow_up(
    thread_id: str, db: Session = Depends(get_db), user: models.User = Depends(current_user),
):
    thread = _thread(thread_id, db)
    if thread.next_follow_up_at is None:
        raise HTTPException(status_code=409, detail="no follow-up scheduled")
    thread.next_follow_up_at = None
    thread.last_follow_up_at = models._now()
    _audit(db, thread_id, user.email, "follow_up_completed", {})
    db.commit()
    db.refresh(thread)
    return thread


@router.get("/{thread_id}/audit", response_model=list[schemas.AuditLogOut])
def list_audit(
    thread_id: str,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    user: models.User = Depends(current_user),
):
    _thread(thread_id, db)
    return db.scalars(
        select(models.AuditLog).where(models.AuditLog.thread_id == thread_id)
        .order_by(models.AuditLog.created_at, models.AuditLog.id).offset(offset).limit(limit)
    ).all()
