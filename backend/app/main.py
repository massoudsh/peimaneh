from contextlib import asynccontextmanager
import os

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import models
from app.auth import current_user
from app.database import engine, get_db
from app.negotiation.state_machine import NegotiationStage
from app.routers import auth, contacts, policy, threads


@asynccontextmanager
async def lifespan(app):
    yield


app = FastAPI(title="پیمانه — Peimaneh API", version="0.3.0", lifespan=lifespan)

_origins = [origin.strip() for origin in os.getenv("CORS_ORIGINS", "http://localhost:8080").split(",") if origin.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.get("/health")
def health(db: Session = Depends(get_db)):
    db.execute(select(1))
    return {"status": "ok", "product": "peimaneh"}


@app.get("/dashboard/summary")
def dashboard_summary(db: Session = Depends(get_db), user: models.User = Depends(current_user)):
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


app.include_router(auth.router)
app.include_router(contacts.router)
app.include_router(threads.router)
app.include_router(policy.router)
