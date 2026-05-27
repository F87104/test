"""CLI runner: load CSV data from the repository and validate the
Elliott Wave 4→5 strategy.

Examples
--------
Run all symbols with default settings:

    python -m elliott45.main --all

Run a specific symbol with custom thresholds:

    python -m elliott45.main --symbol USDJPY --threshold-atr 4 --trades-out trades.csv
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from typing import Optional

import pandas as pd

# Allow `python elliott45/main.py` without installing the package.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from elliott45.src.backtest import BacktestConfig, run_backtest  # noqa: E402
from elliott45.src.data_loader import available_symbols, load_symbol  # noqa: E402
from elliott45.src.elliott import WaveParams, detect_setups  # noqa: E402
from elliott45.src.filters import FilterConfig, apply_filters  # noqa: E402
from elliott45.src.metrics import compute  # noqa: E402


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Elliott Wave 4→5 backtester")
    p.add_argument("--repo-root", default=os.getcwd(),
                   help="Path to the repository root that holds the CSV data")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--symbol", help="A single symbol, e.g. USDJPY")
    g.add_argument("--all", action="store_true", help="Run every known symbol")

    p.add_argument("--threshold-atr", type=float, default=3.0)
    p.add_argument("--atr-period", type=int, default=14)
    p.add_argument("--r2-min", type=float, default=0.236)
    p.add_argument("--r2-max", type=float, default=0.886)
    p.add_argument("--r4-min", type=float, default=0.118)
    p.add_argument("--r4-max", type=float, default=0.618)
    p.add_argument("--target-w1-mult", type=float, default=1.0)

    p.add_argument("--risk-per-trade", type=float, default=0.01)
    p.add_argument("--starting-equity", type=float, default=10_000.0)
    p.add_argument("--max-pending-bars", type=int, default=24)
    p.add_argument("--max-hold-bars", type=int, default=240)
    p.add_argument("--no-short", action="store_true")
    p.add_argument("--fixed-sizing", action="store_true", help="Size each trade off the starting equity (no compounding)")
    p.add_argument("--stop-buffer-frac", type=float, default=0.5)
    p.add_argument("--entry-buffer-frac", type=float, default=0.2)
    # --- filters (off by default) ---
    p.add_argument("--filter-trend", action="store_true", help="Only longs above EMA, only shorts below")
    p.add_argument("--trend-ema-period", type=int, default=200)
    p.add_argument("--filter-atr-regime", action="store_true")
    p.add_argument("--atr-low-pct", type=float, default=0.20)
    p.add_argument("--atr-high-pct", type=float, default=0.97)
    p.add_argument("--filter-w3-strength", action="store_true")
    p.add_argument("--w3-min-ratio", type=float, default=1.272)
    p.add_argument("--filter-alternation", action="store_true")
    p.add_argument("--alternation-min-diff", type=float, default=0.20)
    p.add_argument("--filter-min-rr", action="store_true")
    p.add_argument("--min-rr", type=float, default=1.50)

    # --- exit improvements ---
    p.add_argument("--partial-tp-r", type=float, default=0.0,
                   help="Take part of position at this R-multiple; 0 = disabled")
    p.add_argument("--partial-tp-size", type=float, default=0.5)
    p.add_argument("--no-be-at-partial", action="store_true",
                   help="Do NOT move SL to breakeven when partial fires")
    p.add_argument("--trail-atr-mult", type=float, default=0.0,
                   help="Chandelier-style trailing stop in ATR units; 0 = disabled")
    p.add_argument("--trail-atr-period", type=int, default=14)
    p.add_argument("--trail-after-partial-only", action="store_true")
    p.add_argument("--cost-per-trade", type=float, default=0.0, help="Round-trip cost in price units (spread + commission)")
    p.add_argument("--slippage-atr-mult", type=float, default=0.0, help="One-sided ATR slippage applied AGAINST us on entry/SL/trail/partial")

    p.add_argument("--trades-out", default=None,
                   help="Optional CSV path to dump trade log")
    p.add_argument("--summary-out", default=None,
                   help="Optional JSON path to dump per-symbol metrics summary")
    return p.parse_args()


def run_one(symbol: str, args: argparse.Namespace) -> tuple[Optional[dict], list]:
    try:
        loaded = load_symbol(symbol, args.repo_root)
    except (FileNotFoundError, KeyError) as e:
        print(f"[{symbol}] skipped: {e}")
        return None, []
    df = loaded.df
    if len(df) < 200:
        print(f"[{symbol}] skipped: only {len(df)} bars")
        return None, []
    params = WaveParams(
        r2_min=args.r2_min,
        r2_max=args.r2_max,
        r4_min=args.r4_min,
        r4_max=args.r4_max,
        target_w1_mult=args.target_w1_mult,
        stop_buffer_frac=args.stop_buffer_frac,
        entry_buffer_frac=args.entry_buffer_frac,
    )
    setups = detect_setups(
        df,
        threshold_atr=args.threshold_atr,
        atr_period=args.atr_period,
        params=params,
    )
    raw_setup_count = len(setups)
    fcfg = FilterConfig(
        use_trend=args.filter_trend,
        trend_ema_period=args.trend_ema_period,
        use_atr_regime=args.filter_atr_regime,
        atr_low_pct=args.atr_low_pct,
        atr_high_pct=args.atr_high_pct,
        use_w3_strength=args.filter_w3_strength,
        w3_min_ratio=args.w3_min_ratio,
        use_alternation=args.filter_alternation,
        alternation_min_diff=args.alternation_min_diff,
        use_min_rr=args.filter_min_rr,
        min_rr=args.min_rr,
    )
    setups = apply_filters(df, setups, fcfg)
    cfg = BacktestConfig(
        starting_equity=args.starting_equity,
        risk_per_trade=args.risk_per_trade,
        max_pending_bars=args.max_pending_bars,
        max_hold_bars=args.max_hold_bars,
        allow_short=not args.no_short,
        fixed_sizing=args.fixed_sizing,
        partial_tp_r=args.partial_tp_r,
        partial_tp_size=args.partial_tp_size,
        move_be_at_partial=not args.no_be_at_partial,
        trail_atr_mult=args.trail_atr_mult,
        trail_atr_period=args.trail_atr_period,
        trail_after_partial_only=args.trail_after_partial_only,
        cost_per_trade=args.cost_per_trade,
        slippage_atr_mult=args.slippage_atr_mult,
    )
    result = run_backtest(df, setups, cfg)
    metrics = compute(result, args.starting_equity)

    span_start = df["datetime"].iloc[0]
    span_end = df["datetime"].iloc[-1]
    years = (span_end - span_start).total_seconds() / (365.25 * 24 * 3600)
    print(
        f"[{symbol}] bars={len(df):>6}  span={span_start.date()}..{span_end.date()} ({years:.1f}y)  "
        f"setups={len(setups):>4}/{raw_setup_count:<4}  trades={metrics.trades:>3}  "
        f"win={metrics.win_rate*100:5.1f}%  PF={metrics.profit_factor:5.2f}  "
        f"E[R]={metrics.expectancy_r:+5.2f}R  ret={metrics.total_return_pct:+7.2f}%  "
        f"DD={metrics.max_drawdown_pct:6.2f}%  Sharpe={metrics.sharpe_annual:+5.2f}"
    )

    summary = {
        "symbol": symbol,
        "bars": int(len(df)),
        "span_years": round(years, 2),
        "setups": len(setups),
        "raw_setups": raw_setup_count,
        **metrics.as_dict(),
    }
    return summary, result.trades


def main() -> int:
    args = parse_args()
    symbols = available_symbols() if args.all else [args.symbol]
    all_summaries: list[dict] = []
    all_trades: list[tuple[str, list]] = []
    for sym in symbols:
        summary, trades = run_one(sym, args)
        if summary is not None:
            all_summaries.append(summary)
            all_trades.append((sym, trades))

    if args.summary_out and all_summaries:
        os.makedirs(os.path.dirname(args.summary_out) or ".", exist_ok=True)
        with open(args.summary_out, "w") as f:
            json.dump(all_summaries, f, indent=2, default=str)
        print(f"\nSummary written to {args.summary_out}")

    if args.trades_out and all_trades:
        os.makedirs(os.path.dirname(args.trades_out) or ".", exist_ok=True)
        with open(args.trades_out, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow([
                "symbol", "direction", "entry_time", "entry_price",
                "exit_time", "exit_price", "qty", "pnl", "r_multiple",
                "bars_held", "setup_w1", "setup_w3", "reason",
            ])
            for sym, trades in all_trades:
                for t in trades:
                    w.writerow([
                        sym, t.direction, t.entry_time, t.entry_price,
                        t.exit_time, t.exit_price, t.qty, t.pnl, t.r_multiple,
                        t.bars_held, t.setup_w1, t.setup_w3, t.reason,
                    ])
        print(f"Trades written to {args.trades_out}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
