"""Negotiation Stage state machine.

مراحل مذاکره طبق docs/roadmap.md فاز ۳ و
wiki: .noqte/wiki/concepts/negotiation-flow.md
"""
import enum


class NegotiationStage(str, enum.Enum):
    INQUIRY = "inquiry"
    QUOTE = "quote"
    SAMPLE = "sample"
    PAYMENT_TERMS = "payment_terms"
    SHIPPING = "shipping"
    PROFORMA = "proforma"
    CONFIRMATION = "confirmation"


# انتقال‌های مجاز بین مراحل. مذاکره واقعی همیشه خطی نیست
# (مثلاً می‌توان از quote دوباره به quote برگشت بعد از چانه‌زنی)،
# پس هر مرحله اجازه ماندن در خودش یا رفتن به مرحله بعد را دارد.
ALLOWED_TRANSITIONS: dict[NegotiationStage, set[NegotiationStage]] = {
    NegotiationStage.INQUIRY: {NegotiationStage.INQUIRY, NegotiationStage.QUOTE},
    NegotiationStage.QUOTE: {NegotiationStage.QUOTE, NegotiationStage.SAMPLE, NegotiationStage.PAYMENT_TERMS},
    NegotiationStage.SAMPLE: {NegotiationStage.SAMPLE, NegotiationStage.PAYMENT_TERMS, NegotiationStage.QUOTE},
    NegotiationStage.PAYMENT_TERMS: {NegotiationStage.PAYMENT_TERMS, NegotiationStage.SHIPPING, NegotiationStage.QUOTE},
    NegotiationStage.SHIPPING: {NegotiationStage.SHIPPING, NegotiationStage.PROFORMA, NegotiationStage.PAYMENT_TERMS},
    NegotiationStage.PROFORMA: {NegotiationStage.PROFORMA, NegotiationStage.CONFIRMATION, NegotiationStage.SHIPPING},
    NegotiationStage.CONFIRMATION: {NegotiationStage.CONFIRMATION},
}


def can_transition(current: NegotiationStage, target: NegotiationStage) -> bool:
    return target in ALLOWED_TRANSITIONS[current]


class InvalidTransitionError(Exception):
    pass


def transition(current: NegotiationStage, target: NegotiationStage) -> NegotiationStage:
    """مرحله جدید را برمی‌گرداند اگر انتقال مجاز باشد، وگرنه خطا می‌دهد.

    توجه: انتقال به CONFIRMATION همیشه باید توسط انسان انجام شود؛
    این تابع فقط اعتبار state machine را چک می‌کند، نه مجوز انسانی را.
    """
    if not can_transition(current, target):
        raise InvalidTransitionError(f"cannot move from {current} to {target}")
    return target
