"""Fault injection for resilience testing (M7-7). Off by default, admin-only, and it expires by
itself: a forgotten fault cannot stay on. Applies to the /v1 API only, never to /health."""

import asyncio
import random
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal

from fastapi import APIRouter, FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

Mode = Literal["error", "delay"]
MAX_DURATION_S = 900


@dataclass(frozen=True, slots=True)
class Fault:
    mode: Mode
    rate: float
    delay_s: float
    expires_at: float


class FaultState:
    def __init__(
        self,
        clock: Callable[[], float] = time.monotonic,
        rng: random.Random | None = None,
    ) -> None:
        self._clock = clock
        self._rng = rng or random.Random()  # noqa: S311 - fault sampling, not security
        self._fault: Fault | None = None

    def set(self, mode: Mode, rate: float, duration_s: int, delay_s: float) -> Fault:
        fault = Fault(mode, rate, delay_s, self._clock() + duration_s)
        self._fault = fault
        return fault

    def clear(self) -> None:
        self._fault = None

    def current(self) -> Fault | None:
        if self._fault is not None and self._clock() >= self._fault.expires_at:
            self._fault = None
        return self._fault

    def should_fail(self) -> bool:
        fault = self.current()
        return fault is not None and fault.mode == "error" and self._rng.random() < fault.rate

    async def maybe_delay(self) -> None:
        fault = self.current()
        if fault is not None and fault.mode == "delay":
            await asyncio.sleep(fault.delay_s)


class FaultIn(BaseModel):
    mode: Mode
    rate: float = Field(default=1.0, ge=0.0, le=1.0)
    delay_s: float = Field(default=0.0, ge=0.0, le=60.0)
    duration_s: int = Field(default=60, ge=1, le=MAX_DURATION_S)


def install(app: FastAPI, state: FaultState, admin_token: str) -> None:
    @app.middleware("http")
    async def inject(request: Request, call_next: Callable[[Request], object]) -> object:
        if request.url.path.startswith("/v1/"):
            if state.should_fail():
                body = {
                    "code": "ORDER_SYSTEM_UNAVAILABLE",
                    "message": "injected fault",
                    "retryable": True,
                }
                return JSONResponse(status_code=503, content=body)
            await state.maybe_delay()
        return await call_next(request)  # type: ignore[misc]

    app.include_router(_admin(state, admin_token))


def _admin(state: FaultState, admin_token: str) -> APIRouter:
    router = APIRouter(prefix="/admin")

    def guard(token: str | None) -> None:
        if token != admin_token:
            raise HTTPException(status_code=404)

    @router.post("/faults")
    async def set_fault(
        body: FaultIn, x_admin_token: str | None = Header(default=None)
    ) -> dict[str, Any]:
        guard(x_admin_token)
        fault = state.set(body.mode, body.rate, body.duration_s, body.delay_s)
        return {"mode": fault.mode, "rate": fault.rate, "delay_s": fault.delay_s}

    @router.delete("/faults")
    async def clear_fault(x_admin_token: str | None = Header(default=None)) -> dict[str, Any]:
        guard(x_admin_token)
        state.clear()
        return {"cleared": True}

    @router.get("/faults")
    async def get_fault(x_admin_token: str | None = Header(default=None)) -> dict[str, Any]:
        guard(x_admin_token)
        fault = state.current()
        return {"active": fault is not None, "mode": fault.mode if fault else None}

    return router
