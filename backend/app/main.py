from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import models
from app.database import Base, engine, get_db
from app.negotiation.state_machine import NegotiationStage
from app.routers import contacts, policy, threads


@asynccontextmanager
async def lifespan(app):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(title="پیمانه — Peimaneh API", version="0.2.0", lifespan=lifespan)


@app.get("/health")
def health(db: Session = Depends(get_db)):
    db.execute(select(1))
    return {"status": "ok", "product": "peimaneh"}


@app.get("/dashboard/summary")
def dashboard_summary(db: Session = Depends(get_db)):
    stages = {stage.value: 0 for stage in NegotiationStage}
    for stage, count in db.execute(select(models.Thread.stage, func.count()).group_by(models.Thread.stage)):
        stages[stage.value] = count
    due = db.scalar(select(func.count()).select_from(models.Thread).where(
        models.Thread.next_follow_up_at <= models._now(),
        models.Thread.stage != NegotiationStage.CONFIRMATION,
    ))
    total = sum(stages.values())
    return {
        "contacts": db.scalar(select(func.count()).select_from(models.Contact)),
        "threads": total,
        "open_threads": total - stages["confirmation"],
        "due_follow_ups": due,
        "stages": stages,
    }


app.include_router(contacts.router)
app.include_router(threads.router)
app.include_router(policy.router)
