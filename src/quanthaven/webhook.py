from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from datetime import UTC, datetime
from decimal import Decimal
from sqlite3 import IntegrityError
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .broker import forward_to_mock_broker
from .db import get_connection
from .models import SignalRecord


class SignalIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    symbol: str = Field(min_length=1, max_length=20)
    side: str
    qty: Decimal = Field(gt=0)
    price: Decimal = Field(gt=0)
    client_order_id: str | None = Field(default=None, min_length=1, max_length=100)
    timestamp: str | None = None

    @field_validator("side")
    @classmethod
    def validate_side(cls, value: str) -> str:
        normalized = value.lower()
        if normalized not in {"buy", "sell"}:
            raise ValueError("side must be 'buy' or 'sell'")
        return normalized

    @field_validator("symbol")
    @classmethod
    def normalize_symbol(cls, value: str) -> str:
        return value.upper()


class IngestResponse(BaseModel):
    status: str
    signal: dict[str, Any]


def canonical_payload(signal: SignalIn) -> dict[str, str]:
    return {
        "symbol": signal.symbol,
        "side": signal.side,
        "qty": str(signal.qty),
        "price": str(signal.price),
    }


def payload_hash(signal: SignalIn) -> str:
    body = json.dumps(canonical_payload(signal), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def idempotency_key(signal: SignalIn) -> str:
    return signal.client_order_id or payload_hash(signal)


def _row_to_signal(row: Any) -> SignalRecord:
    return SignalRecord(
        id=int(row["id"]),
        symbol=str(row["symbol"]),
        side=str(row["side"]),
        qty=Decimal(str(row["qty"])),
        price=Decimal(str(row["price"])),
        client_order_id=str(row["client_order_id"]),
        payload_hash=str(row["payload_hash"]),
        broker_ref=str(row["broker_ref"]),
        received_at=str(row["received_at"]),
    )


def store_signal(signal: SignalIn, database_path: str | None = None) -> tuple[str, SignalRecord]:
    key = idempotency_key(signal)
    digest = payload_hash(signal)
    now = datetime.now(UTC).isoformat()

    with get_connection(database_path) as connection:
        existing = connection.execute(
            "SELECT * FROM signals WHERE client_order_id = ?",
            (key,),
        ).fetchone()
        if existing is not None:
            stored = _row_to_signal(existing)
            if stored.payload_hash != digest:
                raise ValueError("client_order_id was reused with a different payload.")
            return "duplicate", stored

        execution = forward_to_mock_broker(signal.symbol, signal.side, str(signal.qty), str(signal.price))
        try:
            cursor = connection.execute(
                """
                INSERT INTO signals (
                    symbol, side, qty, price, client_order_id, payload_hash, broker_ref, received_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    signal.symbol,
                    signal.side,
                    str(signal.qty),
                    str(signal.price),
                    key,
                    digest,
                    execution.broker_ref,
                    now,
                ),
            )
        except IntegrityError as exc:
            raise ValueError("Duplicate signal received.") from exc

        stored = SignalRecord(
            id=int(cursor.lastrowid),
            symbol=signal.symbol,
            side=signal.side,
            qty=signal.qty,
            price=signal.price,
            client_order_id=key,
            payload_hash=digest,
            broker_ref=execution.broker_ref,
            received_at=now,
        )
        return "accepted", stored


def list_signals(database_path: str | None = None, limit: int = 100) -> list[SignalRecord]:
    with get_connection(database_path) as connection:
        rows = connection.execute(
            "SELECT * FROM signals ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [_row_to_signal(row) for row in rows]


def signal_to_api_payload(signal: SignalRecord) -> dict[str, object]:
    payload = signal.to_dict()
    payload.pop("payload_hash")
    return payload

