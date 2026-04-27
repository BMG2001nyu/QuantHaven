from __future__ import annotations

import json
import sys
from pathlib import Path

from fastapi.testclient import TestClient


BASE_DIR = Path(__file__).resolve().parent.parent
SRC_DIR = BASE_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from quanthaven.api import app
from quanthaven.backtest import BacktestConfig, load_bars_from_csv, run_backtest, save_backtest_results
from quanthaven.config import get_settings
from quanthaven.db import initialize_database
from quanthaven.reporting import build_summary, render_markdown, write_reports


def reset_outputs() -> None:
    settings = get_settings()
    for path in (
        settings.backtest_results_path,
        settings.report_markdown_path,
        settings.report_html_path,
        settings.database_path,
    ):
        if path.exists():
            path.unlink()


def main() -> None:
    settings = get_settings()
    reset_outputs()
    initialize_database()

    bars = load_bars_from_csv(settings.data_dir / "sample_ohlcv.csv")
    results = run_backtest(
        bars,
        BacktestConfig(
            initial_capital=settings.initial_capital,
            fee_bps_per_side=settings.fee_bps_per_side,
            slippage_bps_per_side=settings.slippage_bps_per_side,
        ),
    )
    save_backtest_results(results)

    client = TestClient(app)
    response = client.post(
        "/webhook/signal",
        json={
            "symbol": "AAPL",
            "side": "buy",
            "qty": "10",
            "price": "202.5",
            "client_order_id": "demo-1",
        },
    )
    response.raise_for_status()

    summary = build_summary()
    write_reports(summary)

    print("=== Backtest Results ===")
    print(json.dumps(results, indent=2))
    print()
    print("=== Webhook Response ===")
    print(json.dumps(response.json(), indent=2))
    print()
    print("=== Report Output ===")
    print(render_markdown(summary))


if __name__ == "__main__":
    main()

