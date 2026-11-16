"""Pydantic schemas برای API — جدا از مدل‌های SQLAlchemy."""
from __future__ import annotations

import datetime

from pydantic import AwareDatetime, BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.models import Channel, MessageSender, MessageStatus
from app.negotiation.state_machine import NegotiationStage


class AuthBootstrap(BaseModel):
    email: EmailStr
    password: str = Field(min_length=12, max_length=200)


class AuthLogin(BaseModel):
    email: str
    password: str


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_at: datetime.datetime


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=12, max_length=200)
    role: str = "sales"


class UserUpdate(BaseModel):
    role: str | None = None
    is_active: bool | None = None


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    email: str
    role: str
    is_active: bool


class ContactCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    company: str | None = Field(default=None, max_length=200)
    country: str | None = Field(default=None, max_length=100)
    preferred_language: str | None = Field(default=None, max_length=50)
    channel: Channel = Channel.OTHER
    is_sensitive: bool = False

    @field_validator("name")
    @classmethod
    def nonblank_name(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("contact name cannot be blank")
        return value


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
    thread_id: str | None
    actor: str
    action: str
    detail: dict
    created_at: datetime.datetime


class MessageCreate(BaseModel):
    sender: MessageSender
    text: str = Field(min_length=1, max_length=50000)
    translated_text: str | None = Field(default=None, max_length=50000)

    @field_validator("text")
    @classmethod
    def nonblank_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("message text cannot be blank")
        return value


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
    product_category: str = Field(min_length=1, max_length=200)
    price_floor: float = Field(gt=0, allow_inf_nan=False)
    max_discount_pct: float = Field(default=0.0, ge=0, le=100, allow_inf_nan=False)
    allowed_payment_terms: list[str] = []
    capacity_notes: str | None = Field(default=None, max_length=5000)
    sensitive_countries: list[str] = []
    sensitive_customers: list[str] = []


class PolicyConfigOut(PolicyConfigCreate):
    model_config = ConfigDict(from_attributes=True)

    id: str
    version: int
    is_active: bool
    created_at: datetime.datetime


class OfferEvaluationRequest(BaseModel):
    price: float = Field(gt=0, allow_inf_nan=False)
    payment_term: str = Field(min_length=1, max_length=200)
    country: str | None = Field(default=None, max_length=100)
    customer_name: str | None = Field(default=None, max_length=200)
    discount_pct: float = Field(default=0.0, ge=0, le=100, allow_inf_nan=False)
    contact_id: str | None = None


class OfferEvaluationResponse(BaseModel):
    status: str
    reasons: list[str]


class StageTransitionRequest(BaseModel):
    target_stage: NegotiationStage


class StageTransitionsOut(BaseModel):
    current_stage: NegotiationStage
    allowed_stages: list[NegotiationStage]
    requires_manager: bool
