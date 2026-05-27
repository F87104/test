#!/usr/bin/env python3
"""Comprehensive grid search across the enhanced backtest engine.

Searches every (level_kind × lookback × exclude_recent × tp_rr × sl_atr_mult ×
session × margin × breakeven × trailing) combination on every symbol that
sits under ``data/`` and ranks results by total return — with sanity
constraints to avoid over-fitting (min_trades, finite PF, capped DD).

Outputs:
- results/_optimize_<ts>/<SYMBOL>_grid.csv      (full ranking)
- results/_optimize_<ts>/<SYMBOL>_top10.csv     (top 10 by total return)
- results/_optimize_<ts>/winners_summary.csv    (best config per symbol)
- results/_optimize_<ts>/robustness.csv         (best config cross-symbol check)
"""
from __future__ import annotations

import itertools
import json
import math
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.backtest import run_backtest
from src.config import BacktestConfig, IndicatorConfig
from src.data_loader import infer_pip_size, infer_symbol, load_csvs
from src.logger import get_logger, setup_logging
from src.metrics import compute_metrics
from src.runner import discover_csvs, group_files_by_symbol

log = get_logger("trendbreak.optimize")


# ----------------------------------------------------------------------
# Search space (be sensible to keep runtime bounded)
# ----------------------------------------------------------------------
GRID = {
    # Indicator: focus on mid-term (proven baseline) + a few long variants
    "level_kind":         ["mid", "long"],
    "lookback_3m":        [360, 480, 720],
    "exclude_recent_3m":  [60, 120, 180],
    "lookback":           [2400, 5000],
    "exclude_recent":     [480, 760],
    # Risk management
    "tp_rr":              [2.0, 3.0],
    "sl_atr_mult":        [2.0, 2.5],
    # Filters
    "session_filter":     [None, ("asia",), ("asia", "ny")],
    "min_breakout_margin_atr": [0.0, 0.5],
    "breakeven_at_r":     [0.0, 1.0],
    "trailing_atr_mult":  [0.0, 2.0],
}

MIN_TRADES = 30           # require statistical meaningfulness
MAX_DD_PCT = 0.20         # discard plans that draw down > 20 %


def _score(metrics: dict) -> float:
    """Composite score that rewards high return but penalises risk."""
    if metrics["n_trades"] < MIN_TRADES:
        return -math.inf
    dd = abs(metrics["max_drawdown_pct"])
    if dd > MAX_DD_PCT:
        return -math.inf
    pf = metrics["profit_factor"]
    if not math.isfinite(pf):
        pf = 5.0
    # primary objective: total return, but reward stability
    return (
        metrics["total_return_pct"] * 1.0       # core: profit
        + 0.10 * max(0.0, metrics["sharpe"])    # bonus: smoothness
        + 0.05 * max(0.0, pf - 1.0)             # bonus: positive edge
        - 0.50 * dd                             # penalty: drawdown
    )


def _ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%SZ")


def _eval(args):
    df_path, params, ts = args
    import pandas as pd  # noqa: F401  (subprocess re-imports)
    from src.backtest import run_backtest
    from src.config import BacktestConfig, IndicatorConfig
    from src.data_loader import load_csvs
    from src.metrics import compute_metrics

    files = sorted(Path(df_path).glob("*.csv"))
    df, _ = load_csvs(files, timezone="UTC")

    icfg = IndicatorConfig(
        lookback=params["lookback"],
        exclude_recent=params["exclude_recent"],
        lookback_3m=params["lookback_3m"],
        exclude_recent_3m=params["exclude_recent_3m"],
        strict_warmup=True,
        pine_compat_mode="intended",
    )
    bcfg = BacktestConfig(
        direction="both",
        level_kind=params["level_kind"],
        sl_mode="atr",
        sl_atr_mult=params["sl_atr_mult"],
        tp_mode="rr",
        tp_rr=params["tp_rr"],
        atr_period=14,
        risk_per_trade_pct=1.0,
        initial_equity=10_000.0,
        session_filter=params["session_filter"],
        min_breakout_margin_atr=params["min_breakout_margin_atr"],
        breakeven_at_r=params["breakeven_at_r"],
        trailing_atr_mult=params["trailing_atr_mult"],
    )
    try:
        icfg.validate()
        bcfg.validate()
        res = run_backtest(df, indicator_cfg=icfg, backtest_cfg=bcfg)
        m = compute_metrics(res.trades_df, res.equity_curve, initial_equity=10_000.0)
        score = _score(m.to_dict())
        row = {**params, **m.to_dict(), "score": score}
        return row
    except Exception as exc:  # noqa: BLE001
        return {**params, "error": str(exc), "score": -math.inf}


def main(workers: int = 8) -> None:
    setup_logging()
    log.info("=== Grid optimisation ===")

    base = Path("data")
    files = discover_csvs(base)
    groups = group_files_by_symbol(files, data_dir=base)
    log.info("found groups: %s", list(groups.keys()))

    out_dir = Path("results") / f"_optimize_{_ts()}"
    out_dir.mkdir(parents=True, exist_ok=True)

    # Build combination list (skip invalid where exclude >= lookback)
    keys = list(GRID.keys())
    values = [GRID[k] for k in keys]
    combos = []
    for combo in itertools.product(*values):
        p = dict(zip(keys, combo))
        if p["exclude_recent"] >= p["lookback"]:
            continue
        if p["exclude_recent_3m"] >= p["lookback_3m"]:
            continue
        # Long-mode skip: levels-of-long-only mode shouldn't iterate mid keys
        if p["level_kind"] == "long":
            # Keep mid keys but their indicator effect is unused — dedupe
            if (p["lookback_3m"], p["exclude_recent_3m"]) != (480, 120):
                continue
        else:
            # Mid-only skip: long-mode keys are unused — dedupe
            if (p["lookback"], p["exclude_recent"]) != (5000, 760):
                continue
        combos.append(p)

    log.info("evaluating %d combos × %d groups = %d runs",
             len(combos), len(groups), len(combos) * len(groups))

    winners = {}
    for sym, sym_files in groups.items():
        log.info("--- symbol: %s (%d files) ---", sym, len(sym_files))
        if not sym_files:
            continue
        folder = sym_files[0].parent
        ts = _ts()
        work = [(str(folder), p, ts) for p in combos]
        rows = []
        completed = 0
        if workers > 1:
            with ProcessPoolExecutor(max_workers=workers) as ex:
                futures = [ex.submit(_eval, w) for w in work]
                for fut in as_completed(futures):
                    rows.append(fut.result())
                    completed += 1
                    if completed % 100 == 0:
                        log.info("  %s: %d / %d done", sym, completed, len(work))
        else:
            for w in work:
                rows.append(_eval(w))

        table = pd.DataFrame(rows).sort_values(
            "score", ascending=False, na_position="last"
        ).reset_index(drop=True)
        full_path = out_dir / f"{sym}_grid.csv"
        table.to_csv(full_path, index=False)
        top = table.head(10).copy()
        top.to_csv(out_dir / f"{sym}_top10.csv", index=False)
        log.info("[%s] best score=%.3f  total_return=%.2f%%  PF=%.2f  DD=%.2f%%  trades=%d",
                 sym,
                 float(table.iloc[0]["score"]) if pd.notna(table.iloc[0]["score"]) else float("nan"),
                 float(table.iloc[0]["total_return_pct"] or 0) * 100,
                 float(table.iloc[0]["profit_factor"] or 0),
                 float(table.iloc[0]["max_drawdown_pct"] or 0) * 100,
                 int(table.iloc[0]["n_trades"] or 0),
                 )
        winners[sym] = {
            "symbol": sym,
            **{k: table.iloc[0].get(k) for k in keys},
            **{k: table.iloc[0].get(k) for k in (
                "n_trades", "win_rate", "profit_factor", "max_drawdown_pct",
                "total_return_pct", "sharpe", "score",
            )},
        }

    pd.DataFrame(list(winners.values())).to_csv(out_dir / "winners_summary.csv", index=False)
    log.info("winners summary → %s/winners_summary.csv", out_dir)

    # Robustness check: apply each symbol's winner to *every* symbol
    rob = []
    for src_sym, src_w in winners.items():
        params = {k: src_w[k] for k in keys}
        for tgt_sym, tgt_files in groups.items():
            row = _eval((str(tgt_files[0].parent), params, ""))
            row_dict = {
                "winner_of": src_sym,
                "applied_to": tgt_sym,
                **params,
            }
            for k in (
                "n_trades", "win_rate", "profit_factor",
                "max_drawdown_pct", "total_return_pct", "sharpe", "expectancy_r",
            ):
                row_dict[k] = row.get(k)
            rob.append(row_dict)
    rob_df = pd.DataFrame(rob)
    rob_df.to_csv(out_dir / "robustness.csv", index=False)
    log.info("robustness matrix → %s/robustness.csv", out_dir)
    log.info("=== done ===")
    print()
    print("=" * 90)
    print("WINNERS PER SYMBOL")
    print("=" * 90)
    for sym, w in winners.items():
        print(f"\n[{sym}]")
        for k, v in w.items():
            if isinstance(v, float):
                print(f"  {k:30s} = {v:.4f}")
            else:
                print(f"  {k:30s} = {v}")
    print()
    print("=" * 90)
    print("ROBUSTNESS  (apply winner of row to symbol in column)")
    print("=" * 90)
    if not rob_df.empty:
        pivot = rob_df.pivot(index="winner_of", columns="applied_to", values="total_return_pct")
        print(pivot.to_string(float_format=lambda v: f"{v*100:.2f}%" if pd.notna(v) else "—"))


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--workers", type=int, default=8)
    args = p.parse_args()
    main(workers=args.workers)
