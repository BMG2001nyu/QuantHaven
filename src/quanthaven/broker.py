from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256


@dataclass(frozen=True, slots=True)
class BrokerExecution:
    broker_ref: str
    status: str
    executed_at: str


def forward_to_mock_broker(symbol: str, side: str, qty: str, price: str) -> BrokerExecution:
    executed_at = datetime.now(UTC).isoformat()
    raw = f"{symbol}:{side}:{qty}:{price}:{executed_at}"
    broker_ref = f"MOCK-{sha256(raw.encode('utf-8')).hexdigest()[:12]}"
    return BrokerExecution(broker_ref=broker_ref, status="filled", executed_at=executed_at)

