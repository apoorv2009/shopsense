"""Closed vocabularies for triage. IssueType follows the D14f taxonomy."""

from enum import StrEnum


class IssueType(StrEnum):
    ORDER_STATUS = "order_status"
    CANCEL_ORDER = "cancel_order"
    CHANGE_ORDER = "change_order"
    TRACK_SHIPMENT = "track_shipment"
    DELIVERY_DELAY = "delivery_delay"
    DAMAGED_OR_DEFECTIVE = "damaged_or_defective"
    WRONG_ITEM = "wrong_item"
    MISSING_ITEM = "missing_item"
    RETURN_REQUEST = "return_request"
    REPLACEMENT_REQUEST = "replacement_request"
    REFUND_REQUEST = "refund_request"
    REFUND_STATUS = "refund_status"
    WARRANTY_CLAIM = "warranty_claim"
    PRODUCT_SAFETY = "product_safety"
    POLICY_QUESTION = "policy_question"
    PAYMENT_ISSUE = "payment_issue"
    COMPLAINT = "complaint"
    REQUEST_HUMAN = "request_human"
    OUT_OF_SCOPE = "out_of_scope"


# Issue types that cannot be actioned without knowing which order
ISSUES_NEEDING_ORDER: frozenset[IssueType] = frozenset(
    {
        IssueType.ORDER_STATUS,
        IssueType.CANCEL_ORDER,
        IssueType.CHANGE_ORDER,
        IssueType.TRACK_SHIPMENT,
        IssueType.DELIVERY_DELAY,
        IssueType.DAMAGED_OR_DEFECTIVE,
        IssueType.WRONG_ITEM,
        IssueType.MISSING_ITEM,
        IssueType.RETURN_REQUEST,
        IssueType.REPLACEMENT_REQUEST,
        IssueType.REFUND_REQUEST,
        IssueType.REFUND_STATUS,
        IssueType.WARRANTY_CLAIM,
    }
)


class Sentiment(StrEnum):
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    FRUSTRATED = "frustrated"
    ANGRY = "angry"


class Urgency(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ProductCategory(StrEnum):
    ELECTRONICS = "electronics"
    APPAREL = "apparel"
    GROCERIES = "groceries"
    HOME_KITCHEN = "home_kitchen"
    BEAUTY = "beauty"


class RiskFlag(StrEnum):
    LEGAL_THREAT = "legal_threat"
    SOCIAL_MEDIA_THREAT = "social_media_threat"
    PRODUCT_SAFETY = "product_safety"
    PROMPT_INJECTION_SUSPECTED = "prompt_injection_suspected"
    ABUSIVE_LANGUAGE = "abusive_language"
    MULTIPLE_ISSUES = "multiple_issues"


class Language(StrEnum):
    ENGLISH = "en"
    HINGLISH = "hinglish"
    OTHER = "other"
