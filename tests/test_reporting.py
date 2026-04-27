from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from quanthaven.backtest import BacktestConfig, load_bars_from_csv, run_backtest, save_backtest_results
from quanthaven.db import initialize_database
from quanthaven.reporting import build_summary, render_html, render_markdown
from quanthaven.webhook import SignalIn, store_signal


class ReportingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = TemporaryDirectory()
        self.database_path = Path(self.temp_dir.name) / "signals.db"
        self.artifacts_dir = Path(self.temp_dir.name) / "artifacts"
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)

        class Settings:
            data_dir = ROOT / "data"
            runtime_dir = Path(self.temp_dir.name)
            artifacts_dir = self.artifacts_dir
            database_path = self.database_path
            backtest_results_path = self.artifacts_dir / "backtest_results.json"
            report_markdown_path = self.artifacts_dir / "report.md"
            report_html_path = self.artifacts_dir / "report.html"

        self.settings = Settings()
        self.config_patch = patch("quanthaven.reporting.get_settings", return_value=self.settings)
        self.backtest_patch = patch("quanthaven.backtest.get_settings", return_value=self.settings)
        self.db_patch = patch("quanthaven.db.get_settings", return_value=self.settings)
        self.config_patch.start()
        self.backtest_patch.start()
        self.db_patch.start()

        initialize_database(self.database_path)

    def tearDown(self) -> None:
        self.db_patch.stop()
        self.backtest_patch.stop()
        self.config_patch.stop()
        self.temp_dir.cleanup()

    def test_summary_renders_markdown_and_html(self) -> None:
        bars = load_bars_from_csv(ROOT / "data" / "sample_ohlcv.csv")
        results = run_backtest(bars, BacktestConfig())
        save_backtest_results(results, self.settings.backtest_results_path)
        store_signal(
            SignalIn(
                symbol="AAPL",
                side="buy",
                qty="1",
                price="101",
                client_order_id="report-1",
            ),
            str(self.database_path),
        )
        summary = build_summary(str(self.database_path))
        markdown = render_markdown(summary)
        html = render_html(summary)
        self.assertIn("Sharpe ratio", markdown)
        self.assertIn("Logged signals: 1", markdown)
        self.assertIn("<html", html)
        self.assertIn("AAPL", html)


if __name__ == "__main__":
    unittest.main()

