from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from .config import get_settings
from .webhook import list_signals, signal_to_api_payload


def build_summary(database_path: str | None = None) -> dict[str, object]:
    settings = get_settings()
    backtest = {}
    if settings.backtest_results_path.exists():
        backtest = json.loads(settings.backtest_results_path.read_text(encoding="utf-8"))
    signals = [signal_to_api_payload(signal) for signal in list_signals(database_path)]
    by_side = dict(Counter(str(signal["side"]) for signal in signals))
    by_symbol = dict(Counter(str(signal["symbol"]) for signal in signals))
    return {
        "backtest": backtest,
        "signals": {
            "count": len(signals),
            "by_side": by_side,
            "by_symbol": by_symbol,
            "latest": signals[:5],
        },
    }


def render_markdown(summary: dict[str, object]) -> str:
    backtest = summary.get("backtest", {})
    signals = summary.get("signals", {})
    lines = [
        "# QuantHaven Assessment Report",
        "",
        "## Backtest",
        f"- Total return: {backtest.get('total_return_pct', 'n/a')}%",
        f"- Win rate: {backtest.get('win_rate_pct', 'n/a')}%",
        f"- Max drawdown: {backtest.get('max_drawdown_pct', 'n/a')}%",
        f"- Number of trades: {backtest.get('number_of_trades', 'n/a')}",
        f"- Sharpe ratio: {backtest.get('sharpe_ratio', 'n/a')}",
        "",
        "## Signals",
        f"- Logged signals: {signals.get('count', 0)}",
        f"- By side: {signals.get('by_side', {})}",
        f"- By symbol: {signals.get('by_symbol', {})}",
    ]
    return "\n".join(lines)


def render_html(summary: dict[str, object]) -> str:
    backtest = summary.get("backtest", {})
    signals = summary.get("signals", {})
    latest_rows = signals.get("latest", [])
    rows = []
    for signal in latest_rows:
        rows.append(
            "<tr>"
            f"<td>{signal['id']}</td>"
            f"<td>{signal['symbol']}</td>"
            f"<td>{signal['side']}</td>"
            f"<td>{signal['qty']}</td>"
            f"<td>{signal['price']}</td>"
            f"<td>{signal['received_at']}</td>"
            "</tr>"
        )
    table_body = "".join(rows) or "<tr><td colspan='6'>No signals logged yet.</td></tr>"
    return f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>QuantHaven Report</title>
    <style>
      :root {{
        --bg: #f7f3ea;
        --panel: #fffdf8;
        --ink: #1f2933;
        --accent: #0f766e;
        --muted: #52606d;
        --line: #d9e2ec;
      }}
      body {{
        margin: 0;
        font-family: Georgia, "Times New Roman", serif;
        background: radial-gradient(circle at top left, #fff8e7, var(--bg));
        color: var(--ink);
      }}
      main {{
        max-width: 960px;
        margin: 0 auto;
        padding: 48px 20px 72px;
      }}
      .hero, .panel {{
        background: var(--panel);
        border: 1px solid var(--line);
        border-radius: 18px;
        box-shadow: 0 12px 40px rgba(15, 23, 42, 0.08);
      }}
      .hero {{
        padding: 28px;
        margin-bottom: 24px;
      }}
      h1, h2 {{
        margin-top: 0;
      }}
      .metrics {{
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
        gap: 14px;
      }}
      .metric {{
        padding: 16px;
        background: #f2f7f7;
        border-radius: 14px;
      }}
      .metric strong {{
        display: block;
        color: var(--accent);
        font-size: 0.9rem;
        margin-bottom: 8px;
      }}
      .panel {{
        padding: 24px;
      }}
      table {{
        width: 100%;
        border-collapse: collapse;
      }}
      th, td {{
        padding: 12px 10px;
        border-bottom: 1px solid var(--line);
        text-align: left;
        font-size: 0.95rem;
      }}
      .meta {{
        color: var(--muted);
      }}
    </style>
  </head>
  <body>
    <main>
      <section class="hero">
        <p class="meta">QuantHaven end-to-end signal pipeline</p>
        <h1>Strategy Report</h1>
        <div class="metrics">
          <div class="metric"><strong>Total Return</strong>{backtest.get("total_return_pct", "n/a")}%</div>
          <div class="metric"><strong>Win Rate</strong>{backtest.get("win_rate_pct", "n/a")}%</div>
          <div class="metric"><strong>Max Drawdown</strong>{backtest.get("max_drawdown_pct", "n/a")}%</div>
          <div class="metric"><strong>Trades</strong>{backtest.get("number_of_trades", "n/a")}</div>
          <div class="metric"><strong>Sharpe</strong>{backtest.get("sharpe_ratio", "n/a")}</div>
          <div class="metric"><strong>Signals Logged</strong>{signals.get("count", 0)}</div>
        </div>
      </section>
      <section class="panel">
        <h2>Recent Signals</h2>
        <table>
          <thead>
            <tr>
              <th>ID</th>
              <th>Symbol</th>
              <th>Side</th>
              <th>Qty</th>
              <th>Price</th>
              <th>Received At</th>
            </tr>
          </thead>
          <tbody>{table_body}</tbody>
        </table>
      </section>
    </main>
  </body>
</html>"""


def write_reports(summary: dict[str, object]) -> tuple[Path, Path]:
    settings = get_settings()
    markdown = render_markdown(summary)
    html = render_html(summary)
    settings.report_markdown_path.write_text(markdown, encoding="utf-8")
    settings.report_html_path.write_text(html, encoding="utf-8")
    return settings.report_markdown_path, settings.report_html_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate QuantHaven reports.")
    parser.add_argument("--database-path", help="Optional override for the SQLite signal database.")
    args = parser.parse_args()
    summary = build_summary(args.database_path)
    markdown_path, html_path = write_reports(summary)
    print(f"Saved markdown report to {markdown_path}")
    print(f"Saved HTML report to {html_path}")


if __name__ == "__main__":
    main()

