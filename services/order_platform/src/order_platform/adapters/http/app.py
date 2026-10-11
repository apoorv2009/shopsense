"""FastAPI routes for the Order Platform (LLD-7)."""

from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass
from typing import Annotated, Any

from fastapi import APIRouter, FastAPI, Header, Query, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from order_platform.adapters.http.schemas import (
    ErrorOut,
    OrderOut,
    OrderSummaryOut,
    QuoteIn,
    QuoteOut,
    RefundIn,
    RefundOut,
    ReplacementIn,
    ShipmentOut,
    order_out,
    quote_out,
    shipment_out,
    summary_out,
)
from order_platform.application.use_cases import (
    OrderQueries,
    RefundCommand,
    ReplacementCommand,
    RequestRefund,
    RequestReplacement,
)
from order_platform.domain.errors import (
    DuplicateRequestError,
    NotAllowedError,
    NotFoundError,
    OrderPlatformError,
    ValidationFailedError,
)

_STATUS = {
    NotFoundError: status.HTTP_404_NOT_FOUND,
    ValidationFailedError: status.HTTP_422_UNPROCESSABLE_CONTENT,
    NotAllowedError: status.HTTP_409_CONFLICT,
    DuplicateRequestError: status.HTTP_409_CONFLICT,
}
CustomerId = Annotated[str, Header(alias="X-Customer-Id", pattern=r"^C\d{4}$")]
Lifespan = Callable[[FastAPI], AbstractAsyncContextManager[None]]
IdempotencyKey = Annotated[str, Header(alias="Idempotency-Key", min_length=8, max_length=128)]


@dataclass(frozen=True, slots=True)
class Services:
    queries: OrderQueries
    refunds: RequestRefund
    replacements: RequestReplacement


def create_app(services: Services, lifespan: Lifespan | None = None) -> FastAPI:
    app = FastAPI(title="ShopSense Order Platform (mock)", version="1.0", lifespan=lifespan)
    app.include_router(_routes(services))
    app.add_exception_handler(OrderPlatformError, _domain_error)
    app.add_exception_handler(RequestValidationError, _validation_error)

    @app.get("/health/live", include_in_schema=False)
    async def live() -> dict[str, str]:
        return {"status": "ok"}

    return app


def _routes(svc: Services) -> APIRouter:
    r = APIRouter(prefix="/v1")

    @r.get("/orders", response_model=list[OrderSummaryOut])
    async def list_orders(customer: CustomerId, limit: int = Query(10, ge=1, le=10)) -> Any:
        return [summary_out(o) for o in await svc.queries.list_orders(customer, limit)]

    @r.get("/orders/{order_no}", response_model=OrderOut)
    async def get_order(order_no: str, customer: CustomerId) -> Any:
        return order_out(await svc.queries.get_order(customer, order_no))

    @r.get("/orders/{order_no}/shipment", response_model=ShipmentOut)
    async def shipment(order_no: str, customer: CustomerId) -> Any:
        return shipment_out(await svc.queries.shipment(customer, order_no))

    @r.get("/orders/{order_no}/refunds", response_model=list[RefundOut])
    async def refunds(order_no: str, customer: CustomerId) -> Any:
        order = await svc.queries.get_order(customer, order_no)
        return [RefundOut.model_validate(r, from_attributes=True) for r in order.refunds]

    @r.post("/orders/{order_no}/refund-quote", response_model=QuoteOut)
    async def quote(order_no: str, body: QuoteIn, customer: CustomerId) -> Any:
        return quote_out(await svc.queries.quote(customer, order_no, body.item_sku, body.reason))

    @r.post("/refunds", response_model=RefundOut, status_code=status.HTTP_201_CREATED)
    async def refund(body: RefundIn, customer: CustomerId, key: IdempotencyKey) -> Any:
        cmd = RefundCommand(
            customer, body.order_no, body.item_sku, body.amount_paise, body.reason, key
        )
        return await svc.refunds.execute(cmd)

    @r.post("/replacements", status_code=status.HTTP_201_CREATED)
    async def replacement(body: ReplacementIn, customer: CustomerId, key: IdempotencyKey) -> Any:
        cmd = ReplacementCommand(customer, body.order_no, body.item_sku, body.reason, key)
        return await svc.replacements.execute(cmd)

    return r


async def _domain_error(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, OrderPlatformError)
    code = next((s for t, s in _STATUS.items() if isinstance(exc, t)), 500)
    return _error(code, exc.code, str(exc), exc.retryable)


async def _validation_error(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, RequestValidationError)
    fields = ", ".join(".".join(str(p) for p in e["loc"]) for e in exc.errors())
    return _error(422, "VALIDATION_ERROR", f"invalid request: {fields}", False)


def _error(http_status: int, code: str, message: str, retryable: bool) -> JSONResponse:
    body = ErrorOut(code=code, message=message, retryable=retryable)
    return JSONResponse(status_code=http_status, content=body.model_dump())
