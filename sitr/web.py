"""Local web UI: FastAPI app serving one static page and three JSON endpoints.

Bound to 127.0.0.1 by `sitr serve`. Responses never contain secrets or the placeholder
mapping. The input size cap is enforced by the boundary, not by request validation, so
oversized input is refused with an audit record instead of a 422.
"""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

from sitr.boundary import process
from sitr.config import DESTINATION_NAME, ConfigError, load_config, load_policy
from sitr.model import API_KEY_ENV, ai_available
from sitr.policy import view

STATIC = Path(__file__).parent / "static"
app = FastAPI(title="sitr", redoc_url=None)


class ProcessRequest(BaseModel):
    text: str
    mode: Literal["offline", "ai"] = "offline"
    # An identifier, not free text: the same shape policy.yaml enforces on declared names.
    destination: str | None = Field(None, pattern=DESTINATION_NAME.pattern)


@app.exception_handler(ConfigError)
def config_error(_: Request, e: ConfigError) -> JSONResponse:
    """Operator misconfiguration, not a user error: say which file and why, from any endpoint."""
    return JSONResponse(status_code=503, content={"detail": str(e)})


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(STATIC / "index.html")


@app.get("/api/capabilities")
def capabilities() -> dict:
    """What this machine can do, so the page never offers a mode that will not work."""
    try:
        policy = load_policy()
        destinations = [view(d) for d in policy.destinations.values()]
        default, policy_ok = policy.default_destination, True
    except ConfigError:
        destinations, default, policy_ok = [], None, False
    available = ai_available() and policy_ok
    if available:
        reason = None
    elif not policy_ok:
        reason = "policy.yaml could not be loaded"
    else:
        reason = f"{API_KEY_ENV} is not set on the server"
    return {
        "ai_available": available,  # a boolean only; the key itself never leaves the process
        "ai_reason": reason,
        "input_max_chars": load_config().input_max_chars,
        "default_destination": default,
        "destinations": destinations,
    }


@app.get("/api/templates")
def templates() -> list[dict]:
    return [asdict(t) for t in load_config().templates]


@app.post("/api/process")
def run(req: ProcessRequest) -> dict:
    return asdict(process(req.text, mode=req.mode, destination=req.destination))
