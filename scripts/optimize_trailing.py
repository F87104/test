#!/usr/bin/env python3
"""Trailing stop optimisation built on top of the relaxed grid winners.

Goal: keep the high trade count from the relaxed grid (~150-280 trades/symbol)
while pushing PF back up from ~1.3-1.8 to 2.0+ by adding:
  - Trailing ATR stop (let winners run further)
  - Break-even move (eliminate losers after +1R favourable move)
  - Tighter initial SL (some combinations)
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
from src.data_loader import load_csvs
from src.logger import get_logger, setup_logging
from src.metrics import compute_metrics
from src.runner import discover_csvs, group_files_by_symbol

log = get_logger("trendbreak.optimize_trailing")


# 各通貨ごとに最良の relaxed プリセットからスタート
BASE = {
    "XAUUSD": dict(level_kind="mid", lookback_3m=240, exclude_recent_3m=30,
                   tp_rr=3.0, session_filter=("asia", "ny"),
                   min_breakout_margin_atr=0.0, reentry_cooldown_bars=0,
                   folder="data/XAUUSD2014-2024", pip_size=0.1),
    "XAGUSD": dict(level_kind="any", lookback_3m=360, exclude_recent_3m=30,
                   tp_rr=3.0, session_filter=None,
                   min_breakout_margin_atr=0.0, reentry_cooldown_bars=24,
                   folder="data/SILVER2014-2024", pip_size=0.01),
    "GBPJPY": dict(level_kind="any", lookback_3m=180, exclude_recent_3m=30,
                   tp_rr=3.0, session_filter=None,
                   min_breakout_margin_atr=0.0, reentry_cooldown_bars=0,
                   folder="data/GBYJPY2014-2024", pip_size=0.01),
    "USDJPY": dict(level_kind="mid", lookback_3m=180, exclude_recent_3m=30,
                   tp_rr=3.0, session_filter=("asia", "ny"),
                   min_breakout_margin_atr=0.3, reentry_cooldown_bars=0,
                   folder="data/USDJPY2014-2024", pip_size=0.01),
    "EURJPY": dict(level_kind="mid", lookback_3m=180, exclude_recent_3m=30,
                   tp_rr=3.0, session_filter=("asia", "ny"),
                   min_breakout_margin_atr=0.0, reentry_cooldown_bars=24,
                   folder="data/EURJPY2014-2024", pip_size=0.01),
}


# トレーリングロジック単独で探索
GRID = {
    "sl_atr_mult":       [1.5, 2.0],          # 緩和版 1.5 が基本
    "breakeven_at_r":    [0.0, 0.5, 1.0],     # BE 移動: 無し / 0.5R / 1R
    "trailing_atr_mult": [0.0, 1.5, 2.0, 3.0],  # トレール: 無し / N×ATR
    "tp_mode_choice":    ["rr3", "trail"],    # rr3=従来TP3.0 / trail=TPなし+trailで利伸ばし
}

MIN_TRADES = 50
MAX_DD_PCT = 0.20


def _score(metrics: dict) -> float:
    n = metrics["n_trades"]
    if n < MIN_TRADES:
        return -math.inf
    dd = abs(metrics["max_drawdown_pct"])
    if dd > MAX_DD_PCT:
        return -math.inf
    pf = metrics["profit_factor"]
    if not math.isfinite(pf):
        pf = 5.0
    if pf < 1.2:
        return -math.inf
    # PF をより重視するスコア
    return (
        metrics["total_return_pct"] * 1.0
        + 0.20 * max(0.0, pf - 1.0)              # PF >1 を厚く加点
        + 0.10 * max(0.0, metrics["sharpe"])
        - 0.50 * dd
    )


def _ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%SZ")


def _eval(args):
    folder, base, p = args
    from pathlib import Path as _Path
    from src.backtest import run_backtest as _run
    from src.config import BacktestConfig as _BC, IndicatorConfig as _IC
    from src.data_loader import load_csvs as _load
    from src.metrics import compute_metrics as _cm
    import math as _math

    files = sorted(_Path(folder).rglob("*.csv"))
    df, _ = _load(files, timezone="UTC")
    icfg = _IC(
        lookback=5000, exclude_recent=760,
        lookback_3m=base["lookback_3m"],
        exclude_recent_3m=base["exclude_recent_3m"],
        strict_warmup=True, pine_compat_mode="intended",
    )
    tp_mode = "rr" if p["tp_mode_choice"] == "rr3" else "none"
    tp_rr   = base["tp_rr"] if p["tp_mode_choice"] == "rr3" else 0.0
    bcfg = _BC(
        direction="both", level_kind=base["level_kind"],
        sl_mode="atr", sl_atr_mult=p["sl_atr_mult"],
        tp_mode=tp_mode, tp_rr=tp_rr, atr_period=14,
        risk_per_trade_pct=1.0, initial_equity=10_000.0,
        session_filter=base["session_filter"],
        min_breakout_margin_atr=base["min_breakout_margin_atr"],
        breakeven_at_r=p["breakeven_at_r"],
        trailing_atr_mult=p["trailing_atr_mult"],
        reentry_cooldown_bars=base["reentry_cooldown_bars"],
    )
    try:
        icfg.validate()
        bcfg.validate()
        res = _run(df, indicator_cfg=icfg, backtest_cfg=bcfg)
        m = _cm(res.trades_df, res.equity_curve, initial_equity=10_000.0)
        return {**p, **m.to_dict(), "score": _score(m.to_dict())}
    except Exception as exc:  # noqa: BLE001
        return {**p, "error": str(exc), "score": -_math.inf}


def main(workers: int = 4):
    setup_logging()
    log.info("=== Trailing Stop Optimisation (on top of relaxed) ===")

    out_dir = Path("results") / f"_optimize_trailing_{_ts()}"
    out_dir.mkdir(parents=True, exist_ok=True)

    # 探索空間
    keys = list(GRID.keys())
    values = [GRID[k] for k in keys]
    combos = [dict(zip(keys, c)) for c in itertools.product(*values)]
    log.info("combos per symbol: %d × %d symbols", len(combos), len(BASE))

    winners = {}
    for sym, base in BASE.items():
        work = [(base["folder"], base, p) for p in combos]
        log.info("--- %s ---", sym)
        rows = []
        with ProcessPoolExecutor(max_workers=workers) as ex:
            for r in ex.map(_eval, work):
                rows.append(r)
        table = pd.DataFrame(rows).sort_values("score", ascending=False, na_position="last").reset_index(drop=True)
        table.to_csv(out_dir / f"{sym}_trailing_grid.csv", index=False)
        table.head(10).to_csv(out_dir / f"{sym}_trailing_top10.csv", index=False)
        top = table.iloc[0]
        log.info("[%s] best: total_ret=%.2f%% PF=%.2f DD=%.2f%% trades=%d  (BE=%.1fR trail=%.1fATR tp=%s SL=%.1fATR)",
                 sym, float(top["total_return_pct"])*100, float(top["profit_factor"]),
                 float(top["max_drawdown_pct"])*100, int(top["n_trades"]),
                 float(top["breakeven_at_r"]), float(top["trailing_atr_mult"]),
                 top["tp_mode_choice"], float(top["sl_atr_mult"]))
        winners[sym] = {"symbol": sym, **{k: top.get(k) for k in keys},
                        **{k: top.get(k) for k in (
                            "n_trades","win_rate","profit_factor","max_drawdown_pct",
                            "total_return_pct","sharpe","expectancy_r","score",
                        )}}

    pd.DataFrame(list(winners.values())).to_csv(out_dir / "winners_summary.csv", index=False)

    print()
    print("=" * 110)
    print("TRAILING STOP OPTIMISATION  — 緩和ベース + BE移動/トレーリング")
    print("=" * 110)
    print(f"{'symbol':<8} {'trades':>7} {'WR':>6} {'PF':>6} {'DD':>8} {'total':>9} {'sl':>4} {'BE':>4} {'trail':>5} {'tp':>5}")
    print("-" * 110)
    for sym, w in winners.items():
        print(f"{sym:<8} {int(w['n_trades']):>7} {w['win_rate']*100:>5.1f}% {w['profit_factor']:>6.2f} {w['max_drawdown_pct']*100:>7.2f}% {w['total_return_pct']*100:>8.2f}% {w['sl_atr_mult']:>4.1f} {w['breakeven_at_r']:>4.1f} {w['trailing_atr_mult']:>5.1f} {w['tp_mode_choice']:>5}")


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--workers", type=int, default=4)
    args = p.parse_args()
    main(workers=args.workers)
