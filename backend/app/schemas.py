"""Pydantic schemas برای API — جدا از مدل‌های SQLAlchemy."""
from __future__ import annotations

import datetime

from pydantic import BaseModel, ConfigDict

from app.models import Channel, MessageSender, MessageStatus
from app.negotiation.state_machine import NegotiationStage


class ContactCreate(BaseModel):
    name: str
    company: str | None = None
    country: str | None = None
    preferred_language: str | None = None
    channel: Channel = Channel.OTHER
    is_sensitive: bool = False


class ContactOut(ContactCreate):
    model_config = ConfigDict(from_attributes=True)

    id: str
    created_at: datetime.datetime


class ThreadCreate(BaseModel):
    contact_id: str


class ThreadOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    contact_id: str
    stage: NegotiationStage
    summary: str | None
    created_at: datetime.datetime
    updated_at: datetime.datetime
    next_follow_up_at: datetime.datetime | None


class MessageCreate(BaseModel):
    sender: MessageSender
    text: str
    translated_text: str | None = None


class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    thread_id: str
    sender: MessageSender
    status: MessageStatus
    text: str
    translated_text: str | None
    created_at: datetime.datetime


class PolicyConfigCreate(BaseModel):
    product_category: str
    price_floor: float
    max_discount_pct: float = 0.0
    allowed_payment_terms: list[str] = []
    capacity_notes: str | None = None
    sensitive_countries: list[str] = []
    sensitive_customers: list[str] = []


class PolicyConfigOut(PolicyConfigCreate):
    model_config = ConfigDict(from_attributes=True)

    id: str
    version: int
    is_active: bool
    created_at: datetime.datetime


class OfferEvaluationRequest(BaseModel):
    price: float
    payment_term: str
    country: str | None = None
    customer_name: str | None = None
    discount_pct: float = 0.0


class OfferEvaluationResponse(BaseModel):
    status: str
    reasons: list[str]
