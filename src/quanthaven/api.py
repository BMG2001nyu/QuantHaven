from __future__ import annotations

from pydantic import ValidationError
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import HTMLResponse

from .config import get_settings
from .db import initialize_database
from .reporting import build_summary, render_html
from .security import verify_signature
from .webhook import IngestResponse, SignalIn, list_signals, signal_to_api_payload, store_signal


app = FastAPI(title="QuantHaven Signal Pipeline", version="2.0.0")


@app.on_event("startup")
def startup() -> None:
    initialize_database()


@app.post("/webhook/signal", response_model=IngestResponse, status_code=200)
async def ingest_signal(request: Request, x_webhook_signature: str | None = Header(default=None)) -> IngestResponse:
    settings = get_settings()
    raw_body = await request.body()
    if not settings.disable_auth and not verify_signature(settings.webhook_secret, raw_body, x_webhook_signature):
        raise HTTPException(status_code=401, detail="invalid signature")

    try:
        payload = SignalIn.model_validate_json(raw_body)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors()) from exc
    try:
        status, record = store_signal(payload)
    except ValueError as exc:
        if "different payload" in str(exc):
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return IngestResponse(status=status, signal=signal_to_api_payload(record))


@app.get("/signals")
def get_signals(limit: int = 100) -> dict[str, object]:
    signals = [signal_to_api_payload(signal) for signal in list_signals(limit=limit)]
    return {"count": len(signals), "signals": signals}


@app.get("/report")
def get_report() -> HTMLResponse:
    summary = build_summary()
    return HTMLResponse(render_html(summary))


@app.get("/report.json")
def get_report_json() -> dict[str, object]:
    return build_summary()
