"""Policy & Guardrail — طبق docs/architecture.md و
wiki: .noqte/wiki/concepts/policy-engine.md

هیچ پیشنهاد قیمت/شرطی نباید بدون عبور از این ماژول به مشتری ارسال شود.
"""
from __future__ import annotations

import enum
from dataclasses import dataclass, field

from app.models import PolicyConfig


class DecisionStatus(str, enum.Enum):
    READY_TO_SEND = "ready_to_send"
    NEEDS_HUMAN_APPROVAL = "needs_human_approval"


@dataclass
class OfferInput:
    price: float
    payment_term: str
    country: str | None = None
    customer_name: str | None = None
    discount_pct: float = 0.0
    contact_is_sensitive: bool = False


@dataclass
class PolicyDecision:
    status: DecisionStatus
    reasons: list[str] = field(default_factory=list)


def _matches(value: str | None, values: list[str] | None) -> bool:
    if not value:
        return False
    normalized = value.strip().casefold()
    return any(normalized == item.strip().casefold() for item in (values or []) if isinstance(item, str))


def evaluate_offer(policy: PolicyConfig, offer: OfferInput) -> PolicyDecision:
    """پیشنهاد را طبق سیاست فعال شرکت ارزیابی می‌کند.

    اگر هر فیلدی نقض شود، کل تصمیم NEEDS_HUMAN_APPROVAL است، نه فقط بخش نقض‌شده.
    فهرست‌های حساس و اصطلاحات پرداخت بدون حساسیت به حروف کوچک/بزرگ مقایسه می‌شوند.
    """
    reasons: list[str] = []

    if offer.contact_is_sensitive:
        reasons.append("contact is marked sensitive")

    if _matches(offer.country, policy.sensitive_countries):
        reasons.append(f"country '{offer.country}' is on sensitive list")

    if _matches(offer.customer_name, policy.sensitive_customers):
        reasons.append(f"customer '{offer.customer_name}' is on sensitive list")

    if offer.price < policy.price_floor:
        reasons.append(f"price {offer.price} is below price floor {policy.price_floor}")

    if offer.discount_pct > policy.max_discount_pct:
        reasons.append(
            f"discount {offer.discount_pct}% exceeds max allowed {policy.max_discount_pct}%"
        )

    if not _matches(offer.payment_term, policy.allowed_payment_terms):
        reasons.append(
            f"payment term '{offer.payment_term}' not in allowed list {policy.allowed_payment_terms}"
        )

    status = DecisionStatus.NEEDS_HUMAN_APPROVAL if reasons else DecisionStatus.READY_TO_SEND
    return PolicyDecision(status=status, reasons=reasons)
