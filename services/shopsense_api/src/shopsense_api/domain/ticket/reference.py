"""A ticket number quoted by the customer, e.g. 'TKT-CH-d18a6b19b3' (chat) or 'TKT-EM-...'."""

import re

_TICKET_REF = re.compile(r"\bTKT-(CH|EM)-([0-9a-f]{6,})\b", re.IGNORECASE)

_STATUS_SENTENCE: dict[str, str] = {
    "pending_human_approval": "is waiting for a specialist to approve the refund.",
    "needs_customer_info": "needs a few more details from you.",
    "handed_off": "is with a specialist, who will get back to you.",
    "parked_human_queue": "is with a specialist, who will follow up.",
    "resolved": "has been resolved.",
    "answered": "has been answered.",
    "rejected": "was not approved. A specialist can explain why.",
    "cannot_help": "could not be completed. Please see the earlier reply on that ticket.",
    "out_of_scope": "was about something I can't help with.",
    "greeting": "was a greeting.",
}
_ORDER_PROMPT = "If you meant your order, please share the order number (ORD-xxxxxx)."


def find_ticket_reference(text: str) -> str | None:
    match = _TICKET_REF.search(text)
    if match is None:
        return None
    return f"TKT-{match.group(1).upper()}-{match.group(2).lower()}"


def status_sentence(ticket_id: str, outcome: str | None) -> str:
    detail = _STATUS_SENTENCE.get(outcome or "", "is in progress.")
    return f"Ticket {ticket_id} {detail} {_ORDER_PROMPT}"
