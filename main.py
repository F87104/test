#!/usr/bin/env python3
"""Entry-point CLI / GUI launcher for the trend-break backtester.

Examples
--------
GUI (auto fall-back to CLI if no display)::

    python main.py --gui

Single-file backtest::

    python main.py --csv data/XAUUSD_1h.csv

Multi-file (results aggregated)::

    python main.py --csv data/XAUUSD_1h.csv data/BTCUSD_1h.csv

**Auto-discover every CSV under a directory (recommended for "全通貨検証")::**

    python main.py --data-dir data/

    # …with arbitrary glob (e.g. only the H1 timeframe):
    python main.py --data-dir data/ --data-pattern "**/*_H1.csv"

    # …also extract any *.zip in the folder first:
    python main.py --data-dir data/ --extract-zip

Override Pine parameters::

    python main.py --csv data/foo.csv --lookback 4000 --exclude-recent 600

Grid search::

    python main.py --csv data/foo.csv --grid \
        --grid-lookback 2000 3000 5000 --grid-exclude 400 760 1200 \
        --workers 4
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

import pandas as pd

from src.config import BacktestConfig, FullConfig, IndicatorConfig, RunConfig
from src.data_loader import infer_pip_size, infer_symbol
from src.logger import setup_logging


# ---------------------------------------------------------------------------
def _build_cfg(args: argparse.Namespace) -> FullConfig:
    if args.config:
        with open(args.config, "r", encoding="utf-8") as f:
            raw = json.load(f)
        cfg = FullConfig.from_dict(raw)
    else:
        cfg = FullConfig()

    # CLI overrides
    if args.lookback:
        cfg.indicator.lookback = args.lookback
    if args.exclude_recent:
        cfg.indicator.exclude_recent = args.exclude_recent
    if args.lookback_3m:
        cfg.indicator.lookback_3m = args.lookback_3m
    if args.exclude_recent_3m:
        cfg.indicator.exclude_recent_3m = args.exclude_recent_3m
    if args.pine_compat_mode:
        cfg.indicator.pine_compat_mode = args.pine_compat_mode
    if args.strict_warmup is not None:
        cfg.indicator.strict_warmup = args.strict_warmup

    if args.direction:
        cfg.backtest.direction = args.direction
    if args.level_kind:
        cfg.backtest.level_kind = args.level_kind
    if args.entry_fill:
        cfg.backtest.entry_fill = args.entry_fill
    if args.sl_mode:
        cfg.backtest.sl_mode = args.sl_mode
    if args.sl_atr_mult is not None:
        cfg.backtest.sl_atr_mult = args.sl_atr_mult
    if args.tp_mode:
        cfg.backtest.tp_mode = args.tp_mode
    if args.tp_rr is not None:
        cfg.backtest.tp_rr = args.tp_rr
    if args.risk_pct is not None:
        cfg.backtest.risk_per_trade_pct = args.risk_pct
    if args.initial_equity is not None:
        cfg.backtest.initial_equity = args.initial_equity
    if args.timezone:
        cfg.run.timezone = args.timezone
    if args.output_dir:
        cfg.run.output_dir = args.output_dir

    cfg.validate()
    return cfg


# ---------------------------------------------------------------------------
def _cli_run(args: argparse.Namespace) -> int:
    setup_logging(level=logging.DEBUG if args.verbose else logging.INFO)
    cfg = _build_cfg(args)
    from src.runner import run_for_csv

    summaries = []
    for csv in args.csv:
        if not Path(csv).exists():
            print(f"[ERROR] CSV not found: {csv}", file=sys.stderr)
            return 2
        cfg.run.symbol = infer_symbol(csv)
        pip = args.pip_size if args.pip_size is not None else infer_pip_size(cfg.run.symbol)
        s = run_for_csv(csv, cfg, pip_size=pip)
        summaries.append(s)
        m = s["metrics"]
        print(
            f"[{s['symbol']}] trades={m['n_trades']} "
            f"winrate={m['win_rate']:.2%} PF={m['profit_factor']:.2f} "
            f"DD={m['max_drawdown_pct']:.2%}  → {s['artefacts']['out_dir']}"
        )

    if len(summaries) > 1:
        agg_path = Path(cfg.run.output_dir) / "aggregate_summary.json"
        agg_path.parent.mkdir(parents=True, exist_ok=True)
        with open(agg_path, "w", encoding="utf-8") as f:
            json.dump(summaries, f, ensure_ascii=False, indent=2, default=str)
        print(f"[AGG] aggregate summary → {agg_path}")
    return 0


def _cli_batch(args: argparse.Namespace) -> int:
    setup_logging(level=logging.DEBUG if args.verbose else logging.INFO)
    cfg = _build_cfg(args)
    from src.runner import run_batch

    if not Path(args.data_dir).exists():
        print(f"[ERROR] data dir not found: {args.data_dir}", file=sys.stderr)
        return 2

    table = run_batch(
        args.data_dir,
        cfg,
        pattern=args.data_pattern,
        extract_zip=args.extract_zip,
        fail_fast=args.fail_fast,
        group_by_folder=args.group_by_folder,
    )
    # Pretty print: subset of useful columns when present
    cols = [
        "group_key", "symbol", "n_files", "rows", "n_trades", "win_rate",
        "profit_factor", "max_drawdown_pct", "total_return_pct",
        "sharpe", "expectancy_r",
    ]
    show = [c for c in cols if c in table.columns]
    print("=" * 90)
    print("Cross-symbol summary (sorted by total return)")
    print("=" * 90)
    if show and not table.empty:
        # Format percent columns prettily
        fmt = table.copy()
        for c in ("win_rate", "max_drawdown_pct", "total_return_pct"):
            if c in fmt.columns:
                fmt[c] = fmt[c].map(lambda v: f"{v*100:.2f}%" if pd.notna(v) else "—")
        for c in ("profit_factor", "sharpe", "expectancy_r"):
            if c in fmt.columns:
                fmt[c] = fmt[c].map(lambda v: f"{v:.3f}" if pd.notna(v) else "—")
        print(fmt[show].to_string(index=False))
    else:
        print(table.to_string(index=False))
    return 0


def _cli_grid(args: argparse.Namespace) -> int:
    setup_logging(level=logging.DEBUG if args.verbose else logging.INFO)
    cfg = _build_cfg(args)
    from src.data_loader import load_csv
    from src.optimizer import grid_search

    if len(args.csv) != 1:
        print("[ERROR] --grid currently supports exactly one --csv", file=sys.stderr)
        return 2
    csv = args.csv[0]
    cfg.run.symbol = infer_symbol(csv)
    pip = args.pip_size if args.pip_size is not None else infer_pip_size(cfg.run.symbol)
    df, _ = load_csv(csv, timezone=cfg.run.timezone)
    grid = {}
    if args.grid_lookback:
        grid["lookback"] = args.grid_lookback
    if args.grid_exclude:
        grid["exclude_recent"] = args.grid_exclude
    if args.grid_lookback_3m:
        grid["lookback_3m"] = args.grid_lookback_3m
    if args.grid_exclude_3m:
        grid["exclude_recent_3m"] = args.grid_exclude_3m
    if not grid:
        print("[ERROR] --grid requires at least one --grid-* range", file=sys.stderr)
        return 2

    table = grid_search(
        df,
        grid=grid,
        backtest_cfg=cfg.backtest,
        base_indicator_cfg=cfg.indicator,
        symbol=cfg.run.symbol,
        pip_size=pip,
        min_trades=args.min_trades,
        workers=args.workers,
    )
    out_dir = Path(cfg.run.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"grid_{cfg.run.symbol}.csv"
    table.to_csv(out_path, index=False)
    print(f"[GRID] {len(table)} combos → {out_path}")
    if not table.empty:
        print(table.head(10).to_string(index=False))
    return 0


# ---------------------------------------------------------------------------
def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Pine Script 大トレンドブレイク検出 — Backtester")
    p.add_argument("--gui", action="store_true", help="launch tkinter GUI (falls back to CLI if no display)")
    p.add_argument("--csv", nargs="*", default=[], help="one or more OHLCV CSV files")
    p.add_argument("--data-dir", default=None,
                   help="auto-discover & backtest every CSV in this directory (recursive)")
    p.add_argument("--data-pattern", default="**/*",
                   help="glob pattern for --data-dir (default '**/*' = recursive)")
    p.add_argument("--extract-zip", action="store_true",
                   help="extract any *.zip in --data-dir before scanning")
    p.add_argument("--fail-fast", action="store_true",
                   help="abort the batch run on the first error (otherwise log and continue)")
    p.add_argument("--no-group-by-folder", dest="group_by_folder",
                   action="store_false", default=True,
                   help="treat every CSV as its own dataset instead of "
                        "concatenating same-symbol files in the same folder "
                        "(default: group, e.g. SILVER_H1_2014…2025.csv → 1 series)")
    p.add_argument("--config", help="JSON config file (e.g. configs/default.json)")
    p.add_argument("--output-dir", default=None)
    p.add_argument("--timezone", default=None)
    p.add_argument("--pip-size", type=float, default=None)
    p.add_argument("--verbose", action="store_true")

    # Indicator overrides
    p.add_argument("--lookback", type=int)
    p.add_argument("--exclude-recent", type=int)
    p.add_argument("--lookback-3m", type=int)
    p.add_argument("--exclude-recent-3m", type=int)
    p.add_argument("--pine-compat-mode", choices=["intended", "literal"], default=None)
    p.add_argument("--strict-warmup", type=lambda s: s.lower() in ("1", "true", "yes"), default=None)

    # Backtest overrides
    p.add_argument("--direction", choices=["both", "long_only", "short_only"], default=None)
    p.add_argument("--level-kind", choices=["long", "mid", "confluence"], default=None)
    p.add_argument("--entry-fill", choices=["next_open", "signal_close"], default=None)
    p.add_argument("--sl-mode", choices=["atr", "fixed_pct", "signal_bar"], default=None)
    p.add_argument("--sl-atr-mult", type=float, default=None)
    p.add_argument("--tp-mode", choices=["rr", "atr", "none"], default=None)
    p.add_argument("--tp-rr", type=float, default=None)
    p.add_argument("--risk-pct", type=float, default=None)
    p.add_argument("--initial-equity", type=float, default=None)

    # Grid search
    p.add_argument("--grid", action="store_true")
    p.add_argument("--grid-lookback", type=int, nargs="*")
    p.add_argument("--grid-exclude", type=int, nargs="*")
    p.add_argument("--grid-lookback-3m", type=int, nargs="*")
    p.add_argument("--grid-exclude-3m", type=int, nargs="*")
    p.add_argument("--min-trades", type=int, default=5)
    p.add_argument("--workers", type=int, default=1)

    args = p.parse_args(argv)

    if args.gui:
        from src.gui import launch_gui

        return launch_gui()
    if args.grid:
        return _cli_grid(args)
    if args.data_dir:
        return _cli_batch(args)
    if args.csv:
        return _cli_run(args)
    p.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
