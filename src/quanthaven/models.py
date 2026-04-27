from __future__ import annotations

from dataclasses import asdict, dataclass
from decimal import Decimal
from typing import Literal


Side = Literal["buy", "sell"]


@dataclass(frozen=True, slots=True)
class Bar:
    date: str
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass(frozen=True, slots=True)
class Trade:
    entry_date: str
    exit_date: str
    entry_price: float
    exit_price: float
    quantity: float
    pnl: float
    return_pct: float

    def to_dict(self) -> dict[str, float | str]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class SignalRecord:
    id: int
    symbol: str
    side: Side
    qty: Decimal
    price: Decimal
    client_order_id: str
    payload_hash: str
    broker_ref: str
    received_at: str

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["qty"] = str(self.qty)
        payload["price"] = str(self.price)
        return payload

