from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import models, schemas
from app.auth import require_manager
from app.database import get_db
from app.policy.engine import OfferInput, evaluate_offer

router = APIRouter(prefix="/policy", tags=["policy"])


def _active_policy(db: Session) -> models.PolicyConfig:
    policy = db.scalar(
        select(models.PolicyConfig)
        .where(models.PolicyConfig.is_active.is_(True))
        .order_by(models.PolicyConfig.version.desc())
    )
    if not policy:
        raise HTTPException(status_code=404, detail="no active policy configured")
    return policy


@router.get("/active", response_model=schemas.PolicyConfigOut)
def get_active_policy(
    db: Session = Depends(get_db), user: models.User = Depends(require_manager),
):
    return _active_policy(db)


@router.post("", response_model=schemas.PolicyConfigOut)
def create_policy_version(
    payload: schemas.PolicyConfigCreate, db: Session = Depends(get_db),
    user: models.User = Depends(require_manager),
):
    """نسخه جدید سیاست می‌سازد و نسخه‌های قبلی را غیرفعال می‌کند.

    نسخه‌بندی حفظ می‌شود تا معلوم باشد یک پیشنهاد قدیمی طبق کدام نسخه تأیید شد.
    شماره نسخه در دیتابیس یکتا است؛ در صورت رقابت هم‌زمان، فقط یک درخواست موفق می‌شود.
    """
    for attempt in range(2):
        last_version = db.scalar(select(models.PolicyConfig.version).order_by(models.PolicyConfig.version.desc()))
        next_version = (last_version or 0) + 1
        db.execute(update(models.PolicyConfig).values(is_active=False))
        policy = models.PolicyConfig(version=next_version, is_active=True, **payload.model_dump())
        db.add(policy)
        try:
            db.flush()
            db.add(models.AuditLog(
                thread_id=None, actor=user.email, action="policy_version_created",
                detail={"policy_id": policy.id, "version": policy.version},
            ))
            db.commit()
        except IntegrityError:
            db.rollback()
            if attempt == 1:
                raise HTTPException(status_code=409, detail="policy version conflict; retry")
            continue
        db.refresh(policy)
        return policy
    raise HTTPException(status_code=409, detail="policy version conflict; retry")


@router.post("/evaluate-offer", response_model=schemas.OfferEvaluationResponse)
def evaluate(
    payload: schemas.OfferEvaluationRequest, db: Session = Depends(get_db),
    user: models.User = Depends(require_manager),
):
    policy = _active_policy(db)
    offer_data = payload.model_dump(exclude={"contact_id"})
    if payload.contact_id:
        contact = db.get(models.Contact, payload.contact_id)
        if not contact:
            raise HTTPException(status_code=404, detail="contact not found")
        offer_data["contact_is_sensitive"] = contact.is_sensitive
        offer_data["country"] = offer_data["country"] or contact.country
        offer_data["customer_name"] = offer_data["customer_name"] or contact.name
    decision = evaluate_offer(policy, OfferInput(**offer_data))
    return schemas.OfferEvaluationResponse(status=decision.status.value, reasons=decision.reasons)
