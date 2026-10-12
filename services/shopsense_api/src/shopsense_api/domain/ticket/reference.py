"""A ticket number quoted by the customer, e.g. 'TKT-CH-d18a6b19b3' (chat) or 'TKT-EM-...'."""

import re

_TICKET_REF = re.compile(r"\bTKT-(CH|EM)-([0-9a-f]{6,})\b", re.IGNORECASE)

_STATUS_SENTENCE: dict[str, str] = {
    "pending_human_approval": "is waiting for a specialist to approve it",
    "needs_customer_info": "needs more details from you",
    "handed_off": "is with a specialist, who will get back to you",
    "parked_human_queue": "is with a specialist, who will follow up",
    "resolved": "has been resolved",
    "answered": "was answered",
    "rejected": "was not approved",
    "cannot_help": "could not be actioned, see the reply on that ticket",
    "out_of_scope": "was outside what I can help with",
    "greeting": "was a greeting",
}


def find_ticket_reference(text: str) -> str | None:
    match = _TICKET_REF.search(text)
    if match is None:
        return None
    return f"TKT-{match.group(1).upper()}-{match.group(2).lower()}"


def status_sentence(ticket_id: str, outcome: str | None) -> str:
    detail = _STATUS_SENTENCE.get(outcome or "", "is in progress")
    return f"Ticket {ticket_id} {detail}."
