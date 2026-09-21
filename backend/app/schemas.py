"""Pydantic schemas برای API — جدا از مدل‌های SQLAlchemy."""
from __future__ import annotations

import datetime

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator

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
    last_follow_up_at: datetime.datetime | None
    next_follow_up_at: datetime.datetime | None

    @field_validator("created_at", "updated_at", "last_follow_up_at", "next_follow_up_at")
    @classmethod
    def utc_timestamp(cls, value):
        if value is not None and value.tzinfo is None:
            return value.replace(tzinfo=datetime.timezone.utc)
        return value


class FollowUpSchedule(BaseModel):
    due_at: AwareDatetime


class AuditLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    thread_id: str
    actor: str
    action: str
    detail: dict
    created_at: datetime.datetime


class MessageCreate(BaseModel):
    sender: MessageSender
    text: str = Field(min_length=1, max_length=50000)

    @field_validator("text")
    @classmethod
    def nonblank_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("message text cannot be blank")
        return value
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
