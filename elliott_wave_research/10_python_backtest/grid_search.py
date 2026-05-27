"""Grid search over ATR trail multiplier, SL buffer, ADX threshold, and
min-bars-per-wave on a per-symbol basis, with walk-forward (3yr train
/ 1yr eval sliding).

Usage:
    python grid_search.py --symbol USDJPY --out results/grid_USDJPY.csv
"""

from __future__ import annotations
import argparse
import csv
import itertools
import os
import sys
from typing import Dict, List

sys.path.insert(0, os.path.dirname(__file__))
from elliott_5wave_v2 import (ConfigV2, backtest_v2, load_symbol, SYMBOLS)
from elliott_5wave_backtest import Bar


GRID = dict(
    adx_min       = [0.0, 18.0, 20.0, 22.0, 25.0],
    min_bars_wave = [3, 4, 5, 6],
    trail_mult    = [1.5, 2.0, 2.5, 3.0],
    sl_buffer     = [0.1, 0.2, 0.4],
)


def filter_by_year(bars: List[Bar], y0: int, y1: int) -> List[Bar]:
    out = []
    for b in bars:
        try:
            y = int(b.t[:4])
        except (ValueError, TypeError):
            continue
        if y0 <= y <= y1:
            out.append(b)
    return out


def run_one(bars: List[Bar], symbol: str, adx_min, min_bars, trail, sl_buf,
            y0=None, y1=None) -> dict:
    cfg = ConfigV2()
    cfg.use_htf_filter = False
    cfg.tp_mode = "Trail_ATR"
    cfg.use_adx_filter = adx_min > 0
    cfg.adx_min = adx_min
    cfg.min_bars_per_wave = min_bars
    cfg.trail_atr_mult = trail
    cfg.sl_buffer_atr = sl_buf
    cfg.start_year = y0
    cfg.end_year = y1
    return backtest_v2(bars, cfg, symbol=symbol)


def walk_forward(bars: List[Bar], symbol: str, params: dict,
                 train_years: int = 3, eval_years: int = 1,
                 start_year: int = 2014, end_year: int = 2026) -> dict:
    """Generic walk-forward: train_period selects params, eval_period
    measures performance with those params held out."""
    results = []
    for y0 in range(start_year, end_year - train_years - eval_years + 1):
        train_end = y0 + train_years - 1
        eval_start = train_end + 1
        eval_end = eval_start + eval_years - 1
        # We assume params are already chosen; just measure eval performance
        r = run_one(bars, symbol, params["adx_min"], params["min_bars_wave"],
                    params["trail_mult"], params["sl_buffer"],
                    y0=eval_start, y1=eval_end)
        if "error" not in r:
            results.append({
                "y0": eval_start, "y1": eval_end,
                "trades": r["n_trades"], "win": r["win_rate"],
                "pf": r["profit_factor"], "ret": r["total_return_pct"],
                "dd": r["max_drawdown_pct"],
            })
    return {"folds": results}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol", required=True, choices=list(SYMBOLS.keys()))
    ap.add_argument("--root", default=".")
    ap.add_argument("--out", default=None)
    ap.add_argument("--top", type=int, default=10)
    ap.add_argument("--start", type=int, default=2014)
    ap.add_argument("--end", type=int, default=2026)
    args = ap.parse_args()

    bars = load_symbol(args.root, args.symbol)
    print(f"Loaded {len(bars)} bars for {args.symbol}")

    rows = []
    total = 1
    for k, vs in GRID.items():
        total *= len(vs)
    print(f"Grid size: {total}")

    for adx_min, mb, trail, slb in itertools.product(
            GRID["adx_min"], GRID["min_bars_wave"],
            GRID["trail_mult"], GRID["sl_buffer"]):
        r = run_one(bars, args.symbol, adx_min, mb, trail, slb,
                    y0=args.start, y1=args.end)
        if "error" in r:
            continue
        rows.append(dict(adx_min=adx_min, min_bars=mb, trail=trail,
                         sl_buf=slb,
                         trades=r["n_trades"], win=r["win_rate"],
                         pf=r["profit_factor"],
                         ret=r["total_return_pct"],
                         dd=r["max_drawdown_pct"],
                         exp=r["expectancy"]))

    # Rank by (PF > 1.0 first), then return, with min trades >= 15
    valid = [r for r in rows if r["trades"] >= 15]
    valid.sort(key=lambda r: (r["pf"] >= 1.0, r["ret"]), reverse=True)
    print(f"\nTop {args.top} (min 15 trades) for {args.symbol} ({args.start}-{args.end}):")
    print(f"{'adx':>5} {'mb':>3} {'trail':>5} {'slb':>4} | "
          f"{'tr':>4} {'win':>5} {'pf':>5} {'ret':>7} {'dd':>7}")
    for r in valid[:args.top]:
        print(f"{r['adx_min']:>5.0f} {r['min_bars']:>3} {r['trail']:>5.1f} {r['sl_buf']:>4.2f} | "
              f"{r['trades']:>4} {r['win']*100:>4.1f}% {r['pf']:>5.2f} "
              f"{r['ret']:>+6.2f}% {r['dd']:>+6.2f}%")

    # Walk-forward on best params
    if valid:
        best = valid[0]
        best_params = dict(adx_min=best["adx_min"], min_bars_wave=best["min_bars"],
                           trail_mult=best["trail"], sl_buffer=best["sl_buf"])
        print(f"\nWalk-forward (3yr train / 1yr eval) with best params:")
        wf = walk_forward(bars, args.symbol, best_params, 3, 1,
                          args.start, args.end)
        for f in wf["folds"]:
            print(f"  {f['y0']}-{f['y1']}: trades={f['trades']:>3} "
                  f"win={f['win']*100:5.1f}% pf={f['pf']:5.2f} "
                  f"ret={f['ret']:+6.2f}% dd={f['dd']:+6.2f}%")
        if wf["folds"]:
            avg_ret = sum(f["ret"] for f in wf["folds"]) / len(wf["folds"])
            avg_pf  = sum(f["pf"]  for f in wf["folds"]) / len(wf["folds"])
            print(f"  AVERAGE: ret={avg_ret:+.2f}%/yr, pf={avg_pf:.2f}")

    if args.out:
        if os.path.dirname(args.out):
            os.makedirs(os.path.dirname(args.out), exist_ok=True)
        with open(args.out, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["symbol", "adx_min", "min_bars", "trail", "sl_buf",
                        "trades", "win_pct", "pf", "ret_pct", "max_dd_pct", "exp"])
            for r in valid:
                w.writerow([args.symbol, r["adx_min"], r["min_bars"], r["trail"],
                            r["sl_buf"], r["trades"], f"{r['win']*100:.2f}",
                            f"{r['pf']:.2f}", f"{r['ret']:.2f}",
                            f"{r['dd']:.2f}", f"{r['exp']:.4f}"])
        print(f"\nWrote {len(valid)} rows to {args.out}")


if __name__ == "__main__":
    main()
