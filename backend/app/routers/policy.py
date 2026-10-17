from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models, schemas
from app.auth import require_manager
from app.database import get_db
from app.policy.engine import OfferInput, evaluate_offer

router = APIRouter(prefix="/policy", tags=["policy"], dependencies=[Depends(require_manager)])


@router.get("/active", response_model=schemas.PolicyConfigOut)
def get_active_policy(db: Session = Depends(get_db)):
    policy = db.scalar(
        select(models.PolicyConfig)
        .where(models.PolicyConfig.is_active.is_(True))
        .order_by(models.PolicyConfig.version.desc())
    )
    if not policy:
        raise HTTPException(status_code=404, detail="no active policy configured")
    return policy


@router.post("", response_model=schemas.PolicyConfigOut)
def create_policy_version(payload: schemas.PolicyConfigCreate, db: Session = Depends(get_db)):
    """نسخه جدید سیاست می‌سازد و نسخه‌های قبلی را غیرفعال می‌کند.

    نسخه‌بندی عمداً حفظ شده تا بشود فهمید یک پیشنهاد قدیمی طبق
    کدام نسخه سیاست تأیید شده بود.
    """
    last = db.scalar(
        select(models.PolicyConfig).order_by(models.PolicyConfig.version.desc())
    )
    next_version = (last.version + 1) if last else 1

    db.query(models.PolicyConfig).update({"is_active": False})

    policy = models.PolicyConfig(
        version=next_version, is_active=True, **payload.model_dump()
    )
    db.add(policy)
    db.commit()
    db.refresh(policy)
    return policy


@router.post("/evaluate-offer", response_model=schemas.OfferEvaluationResponse)
def evaluate(payload: schemas.OfferEvaluationRequest, db: Session = Depends(get_db)):
    policy = db.scalar(
        select(models.PolicyConfig)
        .where(models.PolicyConfig.is_active.is_(True))
        .order_by(models.PolicyConfig.version.desc())
    )
    if not policy:
        raise HTTPException(status_code=404, detail="no active policy configured")

    decision = evaluate_offer(policy, OfferInput(**payload.model_dump()))
    return schemas.OfferEvaluationResponse(status=decision.status.value, reasons=decision.reasons)
