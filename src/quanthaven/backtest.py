from __future__ import annotations

import argparse
import csv
import io
import json
import math
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path

from .config import get_settings
from .models import Bar, Trade


@dataclass(frozen=True, slots=True)
class BacktestConfig:
    fast_period: int = 9
    slow_period: int = 21
    initial_capital: float = 10_000.0
    fee_bps_per_side: float = 5.0
    slippage_bps_per_side: float = 5.0
    interval: str = "1d"


def load_bars_from_csv(path: str | Path) -> list[Bar]:
    rows: list[Bar] = []
    with Path(path).open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            rows.append(
                Bar(
                    date=row["date"],
                    open=float(row["open"]),
                    high=float(row["high"]),
                    low=float(row["low"]),
                    close=float(row["close"]),
                    volume=float(row["volume"]),
                )
            )
    if not rows:
        raise ValueError("No OHLCV rows found in CSV.")
    return rows


def fetch_stooq_daily_history(symbol: str) -> list[Bar]:
    url = f"https://stooq.com/q/d/l/?s={symbol.lower()}&i=d"
    with urllib.request.urlopen(url, timeout=15) as response:
        payload = response.read().decode("utf-8")

    reader = csv.DictReader(io.StringIO(payload))
    rows: list[Bar] = []
    for row in reader:
        if not row.get("Date") or row.get("Close") in {None, "0"}:
            continue
        rows.append(
            Bar(
                date=row["Date"],
                open=float(row["Open"]),
                high=float(row["High"]),
                low=float(row["Low"]),
                close=float(row["Close"]),
                volume=float(row["Volume"]),
            )
        )
    if not rows:
        raise ValueError(f"No OHLCV data returned for symbol '{symbol}'.")
    return rows


def calculate_ema(values: list[float], period: int) -> list[float]:
    if period <= 0:
        raise ValueError("EMA period must be positive.")
    multiplier = 2 / (period + 1)
    ema_values: list[float] = []
    ema = values[0]
    for value in values:
        ema = ((value - ema) * multiplier) + ema
        ema_values.append(ema)
    return ema_values


def _apply_costs(price: float, side: str, config: BacktestConfig) -> float:
    impact = (config.fee_bps_per_side + config.slippage_bps_per_side) / 10_000.0
    if side == "buy":
        return price * (1.0 + impact)
    return price * (1.0 - impact)


def _calculate_max_drawdown(equity_curve: list[float]) -> float:
    peak = equity_curve[0]
    max_drawdown = 0.0
    for value in equity_curve:
        peak = max(peak, value)
        if peak:
            max_drawdown = max(max_drawdown, ((peak - value) / peak) * 100.0)
    return max_drawdown


def _calculate_sharpe(returns: list[float], interval: str) -> float:
    if len(returns) < 2:
        return 0.0
    mean_return = sum(returns) / len(returns)
    variance = sum((value - mean_return) ** 2 for value in returns) / (len(returns) - 1)
    if variance <= 0:
        return 0.0
    scale = 252 ** 0.5 if interval.endswith("d") else 8_760 ** 0.5
    return (mean_return / math.sqrt(variance)) * scale


def run_backtest(bars: list[Bar], config: BacktestConfig) -> dict[str, object]:
    if len(bars) < max(config.fast_period, config.slow_period) + 2:
        raise ValueError("Not enough bars to run the configured strategy.")

    closes = [bar.close for bar in bars]
    ema_fast = calculate_ema(closes, config.fast_period)
    ema_slow = calculate_ema(closes, config.slow_period)

    cash = config.initial_capital
    units = 0.0
    entry_date = ""
    entry_fill = 0.0
    trades: list[Trade] = []
    equity_curve: list[float] = []

    for index, bar in enumerate(bars):
        previous_index = index - 1
        if previous_index >= 1:
            prev_prev_fast = ema_fast[previous_index - 1]
            prev_prev_slow = ema_slow[previous_index - 1]
            prev_fast = ema_fast[previous_index]
            prev_slow = ema_slow[previous_index]
            cross_up = prev_prev_fast <= prev_prev_slow and prev_fast > prev_slow
            cross_down = prev_prev_fast >= prev_prev_slow and prev_fast < prev_slow
        else:
            cross_up = False
            cross_down = False

        if units == 0.0 and cross_up:
            fill_price = _apply_costs(bar.open, "buy", config)
            units = cash / fill_price
            cash = 0.0
            entry_date = bar.date
            entry_fill = fill_price
        elif units > 0.0 and cross_down:
            exit_fill = _apply_costs(bar.open, "sell", config)
            proceeds = units * exit_fill
            pnl = proceeds - (units * entry_fill)
            return_pct = ((exit_fill / entry_fill) - 1.0) * 100.0
            cash = proceeds
            trades.append(
                Trade(
                    entry_date=entry_date,
                    exit_date=bar.date,
                    entry_price=round(entry_fill, 4),
                    exit_price=round(exit_fill, 4),
                    quantity=round(units, 6),
                    pnl=round(pnl, 2),
                    return_pct=round(return_pct, 2),
                )
            )
            units = 0.0
            entry_date = ""
            entry_fill = 0.0

        equity_curve.append(cash + (units * bar.close))

    if units > 0.0:
        exit_fill = _apply_costs(bars[-1].close, "sell", config)
        proceeds = units * exit_fill
        pnl = proceeds - (units * entry_fill)
        return_pct = ((exit_fill / entry_fill) - 1.0) * 100.0
        cash = proceeds
        trades.append(
            Trade(
                entry_date=entry_date,
                exit_date=bars[-1].date,
                entry_price=round(entry_fill, 4),
                exit_price=round(exit_fill, 4),
                quantity=round(units, 6),
                pnl=round(pnl, 2),
                return_pct=round(return_pct, 2),
            )
        )
        equity_curve[-1] = cash

    period_returns: list[float] = []
    for previous, current in zip(equity_curve, equity_curve[1:]):
        if previous:
            period_returns.append((current / previous) - 1.0)

    win_rate = (sum(1 for trade in trades if trade.pnl > 0) / len(trades) * 100.0) if trades else 0.0
    total_return = ((cash / config.initial_capital) - 1.0) * 100.0
    result = {
        "config": asdict(config),
        "starting_capital": round(config.initial_capital, 2),
        "ending_capital": round(cash, 2),
        "total_return_pct": round(total_return, 2),
        "win_rate_pct": round(win_rate, 2),
        "max_drawdown_pct": round(_calculate_max_drawdown(equity_curve), 2),
        "number_of_trades": len(trades),
        "sharpe_ratio": round(_calculate_sharpe(period_returns, config.interval), 4),
        "trades": [trade.to_dict() for trade in trades],
    }
    return result


def save_backtest_results(results: dict[str, object], output_path: str | Path | None = None) -> Path:
    settings = get_settings()
    target = Path(output_path) if output_path else settings.backtest_results_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(results, indent=2), encoding="utf-8")
    return target


def main() -> None:
    settings = get_settings()
    parser = argparse.ArgumentParser(description="Run the QuantHaven EMA crossover backtest.")
    parser.add_argument("--data-file", help="Path to a local OHLCV CSV file.")
    parser.add_argument("--symbol", help="Free Stooq symbol such as aapl.us.")
    parser.add_argument("--interval", default="1d", help="Reporting interval label such as 1d or 1h.")
    args = parser.parse_args()

    if args.data_file:
        bars = load_bars_from_csv(args.data_file)
    elif args.symbol:
        bars = fetch_stooq_daily_history(args.symbol)
    else:
        bars = load_bars_from_csv(settings.data_dir / "sample_ohlcv.csv")

    config = BacktestConfig(
        initial_capital=settings.initial_capital,
        fee_bps_per_side=settings.fee_bps_per_side,
        slippage_bps_per_side=settings.slippage_bps_per_side,
        interval=args.interval,
    )
    results = run_backtest(bars, config)
    output_path = save_backtest_results(results)
    print(f"Saved backtest results to {output_path}")
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()

