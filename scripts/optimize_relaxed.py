#!/usr/bin/env python3
"""Relaxed grid optimisation: explore looser entry conditions to increase
trade count while maintaining profitability.

Differences vs scripts/optimize_best.py:
  - Adds new level_kind="any" (mid OR long)
  - Shorter lookback_3m candidates (180, 240, 360)
  - Smaller exclude_recent_3m candidates (30, 60, 90, 120)
  - Reentry cooldown options (0 = no cooldown, 24 = 1 day)
  - Score function rewards trade count higher (target 50+ trades)
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
from src.data_loader import infer_pip_size, load_csvs
from src.logger import get_logger, setup_logging
from src.metrics import compute_metrics
from src.runner import discover_csvs, group_files_by_symbol

log = get_logger("trendbreak.optimize_relaxed")


# 緩和探索: より広く、より頻繁に取引できる組合せを試す
GRID = {
    "level_kind":              ["mid", "any"],  # any = mid OR long (緩和の鍵)
    "lookback_3m":             [180, 240, 360, 480],
    "exclude_recent_3m":       [30, 60, 90, 120],
    "tp_rr":                   [2.0, 3.0],
    "sl_atr_mult":             [1.5, 2.0, 2.5],
    "session_filter":          [None, ("asia", "ny"), ("asia",)],
    "min_breakout_margin_atr": [0.0, 0.3],
    "reentry_cooldown_bars":   [0, 24],  # 0 = no wait / 24 = 1 day cooldown
}

MIN_TRADES_TARGET = 50  # 目標取引数 (これ以上で満点)
MAX_DD_PCT = 0.25


def _score(metrics: dict) -> float:
    """取引頻度ボーナス付きスコア"""
    n = metrics["n_trades"]
    if n < 20:
        return -math.inf
    dd = abs(metrics["max_drawdown_pct"])
    if dd > MAX_DD_PCT:
        return -math.inf
    pf = metrics["profit_factor"]
    if not math.isfinite(pf):
        pf = 5.0
    if pf < 1.0:
        return -math.inf  # 損失戦略は除外

    # スコア構成:
    #   total_return が中心
    #   取引数ボーナス: 50 件以上で +1.0 まで線形加算
    #   Sharpe ボーナス + PF ボーナス
    #   DD ペナルティ
    freq_bonus = min(1.0, max(0.0, (n - 20) / (MIN_TRADES_TARGET - 20)))
    return (
        metrics["total_return_pct"] * 1.0
        + 0.30 * freq_bonus
        + 0.10 * max(0.0, metrics["sharpe"])
        + 0.05 * max(0.0, pf - 1.0)
        - 0.50 * dd
    )


def _ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%SZ")


def _eval(args):
    df_path, params = args
    import math as _math
    from pathlib import Path as _Path
    from src.backtest import run_backtest as _run
    from src.config import BacktestConfig as _BC, IndicatorConfig as _IC
    from src.data_loader import load_csvs as _load
    from src.metrics import compute_metrics as _cm

    files = sorted(_Path(df_path).rglob("*.csv"))
    df, _ = _load(files, timezone="UTC")
    icfg = _IC(
        lookback=5000, exclude_recent=760,
        lookback_3m=params["lookback_3m"],
        exclude_recent_3m=params["exclude_recent_3m"],
        strict_warmup=True, pine_compat_mode="intended",
    )
    bcfg = _BC(
        direction="both", level_kind=params["level_kind"],
        sl_mode="atr", sl_atr_mult=params["sl_atr_mult"],
        tp_mode="rr", tp_rr=params["tp_rr"], atr_period=14,
        risk_per_trade_pct=1.0, initial_equity=10_000.0,
        session_filter=params["session_filter"],
        min_breakout_margin_atr=params["min_breakout_margin_atr"],
        reentry_cooldown_bars=params["reentry_cooldown_bars"],
    )
    try:
        icfg.validate()
        bcfg.validate()
        res = _run(df, indicator_cfg=icfg, backtest_cfg=bcfg)
        m = _cm(res.trades_df, res.equity_curve, initial_equity=10_000.0)
        score = _score(m.to_dict())
        return {**params, **m.to_dict(), "score": score}
    except Exception as exc:  # noqa: BLE001
        return {**params, "error": str(exc), "score": -_math.inf}


def main(workers: int = 4) -> None:
    setup_logging()
    log.info("=== Relaxed Grid Optimisation ===")

    base = Path("data")
    files = discover_csvs(base)
    groups = group_files_by_symbol(files, data_dir=base)
    log.info("symbols: %s", list(groups.keys()))

    keys = list(GRID.keys())
    values = [GRID[k] for k in keys]
    combos = []
    for combo in itertools.product(*values):
        p = dict(zip(keys, combo))
        if p["exclude_recent_3m"] >= p["lookback_3m"]:
            continue
        combos.append(p)
    log.info("Combos per symbol: %d × %d symbols = %d runs",
             len(combos), len(groups), len(combos) * len(groups))

    out_dir = Path("results") / f"_optimize_relaxed_{_ts()}"
    out_dir.mkdir(parents=True, exist_ok=True)

    winners = {}
    for sym, sym_files in groups.items():
        if not sym_files:
            continue
        folder = sym_files[0].parent
        work = [(str(folder), p) for p in combos]
        log.info("--- %s (%d combos) ---", sym, len(work))
        rows = []
        with ProcessPoolExecutor(max_workers=workers) as ex:
            futures = [ex.submit(_eval, w) for w in work]
            done = 0
            for fut in as_completed(futures):
                rows.append(fut.result())
                done += 1
                if done % 100 == 0:
                    log.info("  %s: %d / %d", sym, done, len(work))

        table = pd.DataFrame(rows).sort_values("score", ascending=False, na_position="last").reset_index(drop=True)
        table.to_csv(out_dir / f"{sym}_relaxed_grid.csv", index=False)
        table.head(10).to_csv(out_dir / f"{sym}_relaxed_top10.csv", index=False)

        top = table.iloc[0]
        log.info("[%s] best: score=%.3f total_ret=%.2f%% PF=%.2f DD=%.2f%% trades=%d",
                 sym, float(top["score"]),
                 float(top["total_return_pct"]) * 100,
                 float(top["profit_factor"]),
                 float(top["max_drawdown_pct"]) * 100,
                 int(top["n_trades"]))
        winners[sym] = {"symbol": sym, **{k: top.get(k) for k in keys},
                        **{k: top.get(k) for k in (
                            "n_trades", "win_rate", "profit_factor",
                            "max_drawdown_pct", "total_return_pct",
                            "sharpe", "expectancy_r", "score",
                        )}}

    pd.DataFrame(list(winners.values())).to_csv(out_dir / "winners_summary.csv", index=False)

    print()
    print("=" * 105)
    print("RELAXED OPTIMISATION  — 取引頻度ボーナス付き")
    print("=" * 105)
    print(f"{'symbol':<8} {'trades':>7} {'WR':>6} {'PF':>6} {'DD':>8} {'total_ret':>10} {'level':>5} {'lb3m':>5} {'ex3m':>5} {'sl':>4} {'rr':>4} {'session':>10} {'margin':>7} {'cool':>5}")
    print("-" * 105)
    for sym, w in winners.items():
        ss = "OFF" if w["session_filter"] is None else "+".join(w["session_filter"])
        print(f"{sym:<8} {int(w['n_trades']):>7} {w['win_rate']*100:>5.1f}% {w['profit_factor']:>6.2f} {w['max_drawdown_pct']*100:>7.2f}% {w['total_return_pct']*100:>9.2f}% {w['level_kind']:>5} {int(w['lookback_3m']):>5} {int(w['exclude_recent_3m']):>5} {w['sl_atr_mult']:>4.1f} {w['tp_rr']:>4.1f} {ss:>10} {w['min_breakout_margin_atr']:>7.2f} {int(w['reentry_cooldown_bars']):>5}")


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--workers", type=int, default=4)
    args = p.parse_args()
    main(workers=args.workers)
