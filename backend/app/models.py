"""مدل‌های داده اصلی — طبق docs/architecture.md بخش Data Layer."""
from __future__ import annotations

import datetime
import enum
import uuid

from sqlalchemy import JSON, DateTime, Enum, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.negotiation.state_machine import NegotiationStage


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


class Channel(str, enum.Enum):
    WHATSAPP = "whatsapp"
    EMAIL = "email"
    LINKEDIN = "linkedin"
    OTHER = "other"


class MessageSender(str, enum.Enum):
    CONTACT = "contact"  # طرف خارجی
    AGENT_DRAFT = "agent_draft"  # پیش‌نویس تولیدشده توسط AI، هنوز ارسال نشده
    HUMAN = "human"  # پیام ارسالی توسط عضو تیم (شامل تأیید پیش‌نویس AI)


class MessageStatus(str, enum.Enum):
    RECEIVED = "received"  # پیام دریافتی از طرف خارجی
    DRAFT_READY = "draft_ready"  # پیش‌نویس AI، داخل سیاست، آماده ارسال
    NEEDS_APPROVAL = "needs_approval"  # پیش‌نویس AI، خارج از سیاست یا حساس
    SENT = "sent"  # نهایتاً توسط انسان ارسال شد


class Contact(Base):
    __tablename__ = "contacts"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String)
    company: Mapped[str | None] = mapped_column(String, nullable=True)
    country: Mapped[str | None] = mapped_column(String, nullable=True)
    preferred_language: Mapped[str | None] = mapped_column(String, nullable=True)
    channel: Mapped[Channel] = mapped_column(Enum(Channel), default=Channel.OTHER)
    is_sensitive: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), default=_now)

    threads: Mapped[list["Thread"]] = relationship(back_populates="contact")


class Thread(Base):
    __tablename__ = "threads"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    contact_id: Mapped[str] = mapped_column(ForeignKey("contacts.id"))
    stage: Mapped[NegotiationStage] = mapped_column(
        Enum(NegotiationStage), default=NegotiationStage.INQUIRY
    )
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )
    last_follow_up_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    next_follow_up_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    contact: Mapped["Contact"] = relationship(back_populates="threads")
    messages: Mapped[list["Message"]] = relationship(
        back_populates="thread", order_by="Message.created_at"
    )


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    thread_id: Mapped[str] = mapped_column(ForeignKey("threads.id"))
    sender: Mapped[MessageSender] = mapped_column(Enum(MessageSender))
    status: Mapped[MessageStatus] = mapped_column(Enum(MessageStatus), default=MessageStatus.RECEIVED)
    text: Mapped[str] = mapped_column(Text)
    translated_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), default=_now)

    thread: Mapped["Thread"] = relationship(back_populates="messages")


class PolicyConfig(Base):
    """سیاست شرکت — نسخه‌دار تا بشود فهمید یک پیشنهاد قدیمی طبق کدام
    نسخه سیاست تأیید شده بود (edge case ذکرشده در wiki/concepts/policy-engine.md).
    """

    __tablename__ = "policy_configs"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    version: Mapped[int] = mapped_column(default=1)
    is_active: Mapped[bool] = mapped_column(default=True)
    product_category: Mapped[str] = mapped_column(String)
    price_floor: Mapped[float] = mapped_column(Float)
    max_discount_pct: Mapped[float] = mapped_column(Float, default=0.0)
    allowed_payment_terms: Mapped[list] = mapped_column(JSON, default=list)
    capacity_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    sensitive_countries: Mapped[list] = mapped_column(JSON, default=list)
    sensitive_customers: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), default=_now)


class AuditLog(Base):
    """هر تصمیم AI و اقدام انسانی مرتبط — برای اعتمادسازی و یادگیری بعدی."""

    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    thread_id: Mapped[str] = mapped_column(ForeignKey("threads.id"))
    actor: Mapped[str] = mapped_column(String)  # "ai" | "human"
    action: Mapped[str] = mapped_column(String)  # مثلاً "propose_quote", "approve", "reject"
    detail: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), default=_now)
