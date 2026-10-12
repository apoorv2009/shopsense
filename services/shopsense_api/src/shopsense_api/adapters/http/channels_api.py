"""Inbound channels (M6): chat and email. Both start the same ticket workflow, so the same
ticket reaches the same decision whichever channel it arrives on (D8, channel parity).

Email is accepted only from a registered customer address (D8d). Duplicate messages map to
the same ticket, so a re-delivered email is not processed twice."""

import hashlib
import json
import uuid
from collections.abc import AsyncIterator
from dataclasses import asdict, replace
from typing import Any

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from shopsense_api.adapters.workflow.runner import TicketRunner, TicketView
from shopsense_api.domain.ticket.reference import find_ticket_reference, status_sentence
from shopsense_api.entrypoints.channels import normalise_address


class ChatTicketIn(BaseModel):
    customer_no: str = Field(pattern=r"^C\d{4}$")
    message: str = Field(min_length=1, max_length=4000)
    # The customer's earlier messages in this conversation, oldest first (context for triage)
    history: list[str] = Field(default_factory=list, max_length=5)


class EmailInboundIn(BaseModel):
    from_address: str = Field(min_length=3, max_length=254)
    subject: str = Field(default="", max_length=300)
    body: str = Field(default="", max_length=8000)
    message_id: str = Field(min_length=1, max_length=300)


class DecisionIn(BaseModel):
    approve: bool
    reviewer: str = Field(min_length=1, max_length=80)


def create_app(lifespan: Any = None, cors_origins: list[str] | None = None) -> FastAPI:
    app = FastAPI(title="ShopSense API", version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins or ["http://localhost:4200"],
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )

    @app.post("/v1/chat/tickets", status_code=201)
    async def chat(body: ChatTicketIn, request: Request) -> dict[str, Any]:
        runner = _runner(request)
        known = await _ticket_status(runner, body.customer_no, body.message)
        if known is not None:
            return _view(known)
        ticket_id = f"TKT-CH-{uuid.uuid4().hex[:10]}"
        view = await runner.start(
            ticket_id, body.customer_no, body.message, channel="chat", history=tuple(body.history)
        )
        return _view(view)

    @app.post("/v1/channels/email/inbound", response_model=None)
    async def email(body: EmailInboundIn, request: Request) -> Any:
        customer = request.app.state.senders.get(normalise_address(body.from_address))
        if customer is None:
            return JSONResponse(
                status_code=202,
                content={"status": "ignored", "reason": "sender is not a registered customer"},
            )
        runner = _runner(request)
        ticket_id = "TKT-EM-" + hashlib.sha256(body.message_id.encode("utf-8")).hexdigest()[:12]
        if await runner.exists(ticket_id):
            return {"status": "duplicate", "ticket_id": ticket_id}
        text = f"{body.subject}\n\n{body.body}".strip()
        view = await runner.start(ticket_id, customer, text, channel="email")
        return _view(view)

    @app.post("/v1/chat/stream")
    async def chat_stream(body: ChatTicketIn, request: Request) -> StreamingResponse:
        """Demo chat endpoint (M8): server-sent events, one per workflow step, then the result."""
        runner = _runner(request)
        known = await _ticket_status(runner, body.customer_no, body.message)
        if known is not None:

            async def status_events() -> AsyncIterator[str]:
                payload = json.dumps({"final": _view(known)}, default=str, ensure_ascii=False)
                yield f"data: {payload}\n\n"

            return StreamingResponse(status_events(), media_type="text/event-stream")
        ticket_id = f"TKT-CH-{uuid.uuid4().hex[:10]}"

        async def events() -> AsyncIterator[str]:
            async for event in runner.stream(
                ticket_id, body.customer_no, body.message, "chat", history=tuple(body.history)
            ):
                payload = json.dumps(event, default=str, ensure_ascii=False)
                yield f"data: {payload}\n\n"

        return StreamingResponse(events(), media_type="text/event-stream")

    @app.get("/v1/tickets/{ticket_id}")
    async def ticket(ticket_id: str, request: Request) -> dict[str, Any]:
        return _view(await _runner(request).view(ticket_id))

    @app.post("/v1/tickets/{ticket_id}/decision")
    async def decision(ticket_id: str, body: DecisionIn, request: Request) -> dict[str, Any]:
        view = await _runner(request).resume(ticket_id, body.approve, body.reviewer)
        return _view(view)

    return app


def _runner(request: Request) -> TicketRunner:
    runner: TicketRunner = request.app.state.runner
    return runner


def _view(view: TicketView) -> dict[str, Any]:
    return asdict(view)


async def _ticket_status(runner: TicketRunner, customer_no: str, message: str) -> TicketView | None:
    """A ticket number in the message, if it belongs to this customer: answered from its status,
    with no new ticket and no model call."""
    ticket_id = find_ticket_reference(message)
    if ticket_id is None:
        return None
    owned = await runner.status_for(customer_no, ticket_id)
    if owned is None:
        return None
    return replace(
        owned,
        outcome="ticket_status",
        reply=status_sentence(ticket_id, owned.outcome),
    )
