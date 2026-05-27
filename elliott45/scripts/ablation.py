"""Ablation runner: compare baseline vs filter/exit variants across all symbols.

Runs the same backtester many times, each time with a different combination
of quality filters / exit modules turned on. Prints a per-symbol summary
and a portfolio-aggregated table sorted by total return.

Usage:
    python -m elliott45.scripts.ablation [--symbols USDJPY,EURJPY]
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from statistics import mean

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from elliott45.src.backtest import BacktestConfig, run_backtest  # noqa: E402
from elliott45.src.data_loader import available_symbols, load_symbol  # noqa: E402
from elliott45.src.elliott import WaveParams, detect_setups  # noqa: E402
from elliott45.src.filters import FilterConfig, apply_filters  # noqa: E402
from elliott45.src.metrics import compute  # noqa: E402


@dataclass
class Variant:
    name: str
    filter_cfg: FilterConfig
    exit_overrides: dict


def variants() -> list[Variant]:
    base_filt = FilterConfig()
    return [
        Variant("baseline", base_filt, {}),

        # ---- single filter ablations ----
        Variant("F: trend (EMA200)", FilterConfig(use_trend=True), {}),
        Variant("F: atr-regime",     FilterConfig(use_atr_regime=True), {}),
        Variant("F: w3-strength",    FilterConfig(use_w3_strength=True), {}),
        Variant("F: alternation",    FilterConfig(use_alternation=True), {}),
        Variant("F: min-RR 1.5",     FilterConfig(use_min_rr=True, min_rr=1.5), {}),
        Variant("F: min-RR 2.0",     FilterConfig(use_min_rr=True, min_rr=2.0), {}),

        # ---- single exit ablations ----
        Variant("X: partial 1R + BE",        base_filt, {"partial_tp_r": 1.0, "partial_tp_size": 0.5, "move_be_at_partial": True}),
        Variant("X: partial 0.6R + BE",      base_filt, {"partial_tp_r": 0.6, "partial_tp_size": 0.5, "move_be_at_partial": True}),
        Variant("X: trail 3xATR",            base_filt, {"trail_atr_mult": 3.0}),
        Variant("X: trail 4xATR after part", base_filt, {"partial_tp_r": 1.0, "trail_atr_mult": 4.0, "trail_after_partial_only": True}),

        # ---- combined ----
        Variant(
            "C: trend + min-RR1.5",
            FilterConfig(use_trend=True, use_min_rr=True, min_rr=1.5),
            {},
        ),
        Variant(
            "C: trend + alternation + min-RR1.5",
            FilterConfig(use_trend=True, use_alternation=True, use_min_rr=True, min_rr=1.5),
            {},
        ),
        Variant(
            "C: trend + partial1R+BE",
            FilterConfig(use_trend=True),
            {"partial_tp_r": 1.0, "partial_tp_size": 0.5, "move_be_at_partial": True},
        ),
        Variant(
            "C: trend + partial1R+BE + trail3xATR",
            FilterConfig(use_trend=True),
            {"partial_tp_r": 1.0, "partial_tp_size": 0.5, "move_be_at_partial": True,
             "trail_atr_mult": 3.0, "trail_after_partial_only": True},
        ),
        Variant(
            "C: ALL filters + partial1R+BE",
            FilterConfig(
                use_trend=True, use_atr_regime=True, use_w3_strength=True,
                use_alternation=True, use_min_rr=True, min_rr=1.5,
            ),
            {"partial_tp_r": 1.0, "partial_tp_size": 0.5, "move_be_at_partial": True},
        ),
    ]


def _run_variant(variant: Variant, symbol: str, df, raw_setups, params):
    setups = apply_filters(df, raw_setups, variant.filter_cfg)
    cfg = BacktestConfig(fixed_sizing=True, **variant.exit_overrides)
    result = run_backtest(df, setups, cfg)
    metrics = compute(result, cfg.starting_equity)
    return setups, metrics


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", default=None,
                    help="Comma-separated list; defaults to all known symbols")
    ap.add_argument("--threshold-atr", type=float, default=3.0)
    ap.add_argument("--atr-period", type=int, default=14)
    ap.add_argument("--out", default="elliott45/results/ablation.json")
    args = ap.parse_args()

    syms = (
        args.symbols.split(",") if args.symbols else available_symbols()
    )

    # Load once per symbol; reuse pivots across variants.
    cache: dict[str, tuple] = {}
    for s in syms:
        try:
            loaded = load_symbol(s, os.getcwd())
        except (FileNotFoundError, KeyError) as e:
            print(f"[{s}] skip: {e}")
            continue
        df = loaded.df
        params = WaveParams()
        setups = detect_setups(
            df, threshold_atr=args.threshold_atr, atr_period=args.atr_period, params=params
        )
        cache[s] = (df, setups, params)
        print(f"loaded {s}: {len(df):,} bars, {len(setups)} raw setups")

    results = []
    for v in variants():
        per_sym = {}
        for s, (df, raw, params) in cache.items():
            kept, m = _run_variant(v, s, df, raw, params)
            per_sym[s] = {
                "raw_setups": len(raw),
                "kept_setups": len(kept),
                "trades": m.trades,
                "win_rate": round(m.win_rate, 4),
                "profit_factor": (
                    round(m.profit_factor, 3) if np.isfinite(m.profit_factor) else None
                ),
                "expectancy_r": round(m.expectancy_r, 3),
                "total_return_pct": round(m.total_return_pct, 2),
                "max_dd_pct": round(m.max_drawdown_pct, 2),
                "sharpe": round(m.sharpe_annual, 2),
            }
        # Portfolio aggregates (simple averages across symbols).
        wins = [p["win_rate"] for p in per_sym.values() if p["trades"] > 0]
        pfs = [p["profit_factor"] for p in per_sym.values()
               if p["profit_factor"] is not None]
        exps = [p["expectancy_r"] for p in per_sym.values() if p["trades"] > 0]
        rets = [p["total_return_pct"] for p in per_sym.values()]
        dds = [p["max_dd_pct"] for p in per_sym.values()]
        shs = [p["sharpe"] for p in per_sym.values()]
        trades = [p["trades"] for p in per_sym.values()]
        agg = {
            "variant": v.name,
            "mean_win_rate": round(mean(wins), 4) if wins else 0.0,
            "mean_pf": round(mean(pfs), 3) if pfs else None,
            "mean_exp_R": round(mean(exps), 3) if exps else 0.0,
            "mean_total_ret_pct": round(mean(rets), 2) if rets else 0.0,
            "mean_max_dd_pct": round(mean(dds), 2) if dds else 0.0,
            "mean_sharpe": round(mean(shs), 2) if shs else 0.0,
            "total_trades": sum(trades),
            "per_symbol": per_sym,
        }
        results.append(agg)
        print(
            f"{v.name:<42} "
            f"trades={agg['total_trades']:>5}  "
            f"win={agg['mean_win_rate']*100:5.1f}%  "
            f"PF={agg['mean_pf'] if agg['mean_pf'] is not None else 'inf':>5}  "
            f"E[R]={agg['mean_exp_R']:+5.2f}  "
            f"ret={agg['mean_total_ret_pct']:+7.2f}%  "
            f"DD={agg['mean_max_dd_pct']:6.2f}%  "
            f"Sharpe={agg['mean_sharpe']:+5.2f}"
        )

    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nWritten {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
