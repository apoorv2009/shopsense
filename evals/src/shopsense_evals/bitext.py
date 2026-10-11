"""Bitext retail dataset loading and the D14f intent → issue-type mapping."""

import csv
from dataclasses import dataclass
from pathlib import Path

# D14f mapping (docs/adr/014-evaluation-and-data.md)
BITEXT_TO_ISSUE: dict[str, str] = {
    "track_order": "order_status",
    "cancel_order": "cancel_order",
    "change_order": "change_order",
    "track_delivery": "track_shipment",
    "delivery_issue": "delivery_delay",
    "damaged_delivery": "damaged_or_defective",
    "product_issue": "damaged_or_defective",
    "wrong_item": "wrong_item",
    "missing_item": "missing_item",
    "return_product": "return_request",
    "return_product_online": "return_request",
    "return_product_in_store": "return_request",
    "exchange_product": "replacement_request",
    "exchange_product_in_store": "replacement_request",
    "request_refund": "refund_request",
    "refund_status": "refund_status",
    "return_policy": "policy_question",
    "refund_policy": "policy_question",
    "delivery_time": "policy_question",
    "shipping_costs": "policy_question",
    "payment_methods": "policy_question",
    "payment_issue": "payment_issue",
    "submit_feedback": "complaint",
    "human_agent": "request_human",
}
OUT_OF_SCOPE_INTENTS = frozenset(
    {"change_account", "recover_password", "add_product", "store_opening_hours", "use_app"}
)

# Issue types a reasonable labeller could choose for the same generated ticket
EQUIVALENT_ISSUES: tuple[frozenset[str], ...] = (
    frozenset({"order_status", "track_shipment", "delivery_delay"}),
    frozenset({"return_request", "refund_request"}),
    frozenset({"replacement_request", "return_request"}),
    frozenset({"damaged_or_defective", "warranty_claim"}),
    frozenset({"wrong_item", "missing_item"}),
)


@dataclass(frozen=True, slots=True)
class BitextRow:
    instruction: str
    intent: str


def load_rows(path: Path) -> list[BitextRow]:
    with path.open(encoding="utf-8", newline="") as handle:
        return [BitextRow(r["instruction"], r["intent"]) for r in csv.DictReader(handle)]


def accepted_issue_types(issue_type: str) -> frozenset[str]:
    accepted = {issue_type}
    for group in EQUIVALENT_ISSUES:
        if issue_type in group:
            accepted |= group
    return frozenset(accepted)
