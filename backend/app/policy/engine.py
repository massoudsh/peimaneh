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


@dataclass
class PolicyDecision:
    status: DecisionStatus
    reasons: list[str] = field(default_factory=list)


def evaluate_offer(policy: PolicyConfig, offer: OfferInput) -> PolicyDecision:
    """پیشنهاد را طبق سیاست فعال شرکت ارزیابی می‌کند.

    قانون edge case: اگر حتی یک فیلد نقض شود، کل تصمیم
    NEEDS_HUMAN_APPROVAL می‌شود، نه فقط بخش نقض‌شده.
    """
    reasons: list[str] = []

    if offer.country and offer.country in policy.sensitive_countries:
        reasons.append(f"country '{offer.country}' is on sensitive list")

    if offer.customer_name and offer.customer_name in policy.sensitive_customers:
        reasons.append(f"customer '{offer.customer_name}' is on sensitive list")

    if offer.price < policy.price_floor:
        reasons.append(
            f"price {offer.price} is below price floor {policy.price_floor}"
        )

    if offer.discount_pct > policy.max_discount_pct:
        reasons.append(
            f"discount {offer.discount_pct}% exceeds max allowed {policy.max_discount_pct}%"
        )

    if offer.payment_term not in policy.allowed_payment_terms:
        reasons.append(
            f"payment term '{offer.payment_term}' not in allowed list {policy.allowed_payment_terms}"
        )

    status = DecisionStatus.NEEDS_HUMAN_APPROVAL if reasons else DecisionStatus.READY_TO_SEND
    return PolicyDecision(status=status, reasons=reasons)
