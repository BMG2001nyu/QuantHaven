from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from quanthaven.backtest import BacktestConfig, calculate_ema, load_bars_from_csv, run_backtest


class BacktestTests(unittest.TestCase):
    def test_calculate_ema_returns_same_length(self) -> None:
        values = [1, 2, 3, 4, 5]
        ema = calculate_ema(values, 3)
        self.assertEqual(len(ema), len(values))
        self.assertGreater(ema[-1], ema[0])

    def test_backtest_returns_requested_metrics(self) -> None:
        bars = load_bars_from_csv(ROOT / "data" / "sample_ohlcv.csv")
        results = run_backtest(bars, BacktestConfig())
        self.assertIn("total_return_pct", results)
        self.assertIn("win_rate_pct", results)
        self.assertIn("max_drawdown_pct", results)
        self.assertIn("number_of_trades", results)
        self.assertIn("sharpe_ratio", results)
        self.assertGreaterEqual(results["number_of_trades"], 1)

    def test_backtest_uses_next_bar_execution(self) -> None:
        bars = load_bars_from_csv(ROOT / "data" / "sample_ohlcv.csv")
        results = run_backtest(bars, BacktestConfig())
        first_trade = results["trades"][0]
        self.assertEqual(first_trade["entry_date"], "2024-01-04")


if __name__ == "__main__":
    unittest.main()

