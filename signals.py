#!/usr/bin/env python3
"""Semi-automatic signal scanner — CLI entry point.

Usage
-----
    # Scan once with the default watch list
    python signals.py

    # Use a custom watch list
    python signals.py --watch configs/watch_list.json

    # Show every fired signal in the last N bars (default 240 ≈ 10 days of H1)
    python signals.py --lookback-bars 480

    # Output as JSON (machine-readable, for piping to webhooks etc.)
    python signals.py --format json

    # Save to CSV for record-keeping
    python signals.py --csv-out results/signals_$(date +%F).csv

    # Combine all three
    python signals.py --watch configs/watch_list.json --lookback-bars 240 \
                      --csv-out results/today_signals.csv

Output
------
- "★ NEW" signals = freshest (=last bar) signals you must consider immediately
- "+Nb"  = signal fired N bars ago (already actionable / in-progress)
- A summary table at the end
- Optional CSV containing every signal in the scanned window
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.logger import setup_logging
from src.signal_scanner import (
    Signal,
    WatchItem,
    format_signal_human,
    format_signal_oneline,
    scan_symbol,
)


def _load_watch_list(path: Path) -> list[dict]:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    items = data.get("items") if isinstance(data, dict) else data
    if not items:
        raise ValueError(f"[ERR-CONFIG] watch list at {path} has no items")
    return items


def _print_header() -> None:
    print()
    print("╔" + "═" * 76 + "╗")
    print("║" + "  Trend-Break Signal Scanner — 半自動シグナル抽出".center(76) + "║")
    print("╚" + "═" * 76 + "╝")
    print()


def _print_summary_table(all_signals: list[tuple[Signal, bool]]) -> None:
    print()
    print("━" * 78)
    print("  シグナル要約 (NEW = 最新バー / +Nb = N バー前に発火)")
    print("━" * 78)
    if not all_signals:
        print("  シグナルなし。市場様子見。")
        print("━" * 78)
        return
    for sig, fresh in all_signals:
        print(format_signal_oneline(sig, fresh=fresh))
    print("━" * 78)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Semi-automatic trend-break signal scanner")
    p.add_argument("--watch", default="configs/watch_list.json",
                   help="path to watch list JSON (default: configs/watch_list.json)")
    p.add_argument("--lookback-bars", type=int, default=240,
                   help="how many recent bars to scan per symbol (default 240 ≈ 10 days of H1)")
    p.add_argument("--format", choices=["human", "json"], default="human",
                   help="output format (default: human-readable)")
    p.add_argument("--csv-out", default=None,
                   help="optional path to write all signals as CSV")
    p.add_argument("--quiet", action="store_true",
                   help="suppress per-symbol detail printout (only show summary)")
    p.add_argument("--verbose", action="store_true")
    args = p.parse_args(argv)

    setup_logging(level=logging.DEBUG if args.verbose else logging.WARNING)

    items = _load_watch_list(Path(args.watch))
    all_recent: list[tuple[Signal, bool]] = []
    fresh_signals: list[Signal] = []
    all_signals_for_csv: list[Signal] = []
    json_payload: list[dict] = []

    if args.format == "human":
        _print_header()

    for it in items:
        sym = it.get("symbol", "?")
        try:
            watch = WatchItem.from_dict(it)
            freshest, recent = scan_symbol(
                watch,
                lookback_bars=args.lookback_bars,
                backtest_pf=it.get("backtest_pf"),
                backtest_win_rate=it.get("backtest_win_rate"),
            )
        except Exception as exc:  # noqa: BLE001
            if args.format == "human":
                print(f"[ERROR] {sym}: {exc}")
            else:
                json_payload.append({"symbol": sym, "error": str(exc)})
            continue

        # The "freshest" signal is on the very last bar IFF bars_since_signal == 0
        is_fresh = (freshest is not None) and (freshest.bars_since_signal == 0)
        if is_fresh:
            fresh_signals.append(freshest)
        for s in recent:
            all_recent.append((s, s.bars_since_signal == 0))
            all_signals_for_csv.append(s)

        if args.format == "human" and not args.quiet:
            if not recent:
                print(f"\n[ {sym} ] シグナルなし (直近 {args.lookback_bars} バー)")
                continue
            print(f"\n[ {sym} ] 直近 {args.lookback_bars} バーで {len(recent)} 個発火")
            # Show top 3 most recent in detail
            for s in recent[:3]:
                print(format_signal_human(s, fresh=(s.bars_since_signal == 0)))
            if len(recent) > 3:
                print(f"  …他に {len(recent)-3} 個 (詳細は --csv-out で保存)")
        elif args.format == "json":
            json_payload.append({
                "symbol": sym,
                "freshest": freshest.to_dict() if freshest else None,
                "recent": [s.to_dict() for s in recent],
            })

    # Summary
    if args.format == "human":
        _print_summary_table(all_recent)
        if fresh_signals:
            print()
            print("⚠️  最新バーに " + str(len(fresh_signals)) + " 個のシグナルがあります:")
            for s in fresh_signals:
                print(f"     - {s.symbol} {s.direction.upper()} @ {s.proposed_entry_price:.5f}")
            print()
    elif args.format == "json":
        print(json.dumps(json_payload, ensure_ascii=False, indent=2, default=str))

    # CSV output
    if args.csv_out and all_signals_for_csv:
        rows = [s.to_dict() for s in all_signals_for_csv]
        df = pd.DataFrame(rows)
        Path(args.csv_out).parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(args.csv_out, index=False)
        if args.format == "human":
            print(f"  → CSV 保存: {args.csv_out} ({len(rows)} signals)")

    return 0 if not fresh_signals else 0  # always 0; users use exit-code-free


if __name__ == "__main__":
    sys.exit(main())
