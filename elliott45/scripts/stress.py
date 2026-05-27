"""Strict stress-test runner.

For every symbol in the repo, runs the *tuned* exit configuration
(partial 1R + breakeven, trail 2xATR) under several "厳しめ" overlays:

  * Realistic per-symbol round-trip spread (``src/costs.REALISTIC_COSTS``)
  * Strict per-symbol spread (~2x realistic)
  * ATR slippage applied AGAINST us on entry / SL / trail / partial fills
  * Combined: strict spread + 0.10/0.20/0.30 x ATR slippage

Then for the worst-case combined run we report:
  * Year-by-year P&L breakdown (does the edge survive every regime?)
  * Monte Carlo bootstrap on trade ordering -> 95th-percentile max DD
  * Risk-per-trade sensitivity (1% / 2% / 3% / 5%)

Outputs ``elliott45/results/stress.json`` + a console table.
"""

from __future__ import annotations

import json
import os
import sys
from collections import defaultdict
from statistics import mean

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from elliott45.src.backtest import BacktestConfig, BacktestResult, Trade, run_backtest  # noqa: E402
from elliott45.src.costs import REALISTIC_COSTS, STRICT_COSTS  # noqa: E402
from elliott45.src.data_loader import available_symbols, load_symbol  # noqa: E402
from elliott45.src.elliott import WaveParams, detect_setups  # noqa: E402
from elliott45.src.metrics import compute  # noqa: E402


TUNED_EXIT = dict(
    partial_tp_r=1.0,
    partial_tp_size=0.5,
    move_be_at_partial=True,
    trail_atr_mult=2.0,
    trail_atr_period=14,
)


def _run(df, setups, **overrides) -> BacktestResult:
    cfg = BacktestConfig(fixed_sizing=True, **TUNED_EXIT, **overrides)
    return run_backtest(df, setups, cfg)


def _row(symbol: str, label: str, res: BacktestResult, equity_start: float) -> dict:
    m = compute(res, equity_start)
    pf = m.profit_factor if np.isfinite(m.profit_factor) else None
    return {
        "symbol": symbol,
        "scenario": label,
        "trades": m.trades,
        "win": round(m.win_rate, 4),
        "pf": round(pf, 2) if pf is not None else None,
        "exp_r": round(m.expectancy_r, 3),
        "ret_pct": round(m.total_return_pct, 2),
        "dd_pct": round(m.max_drawdown_pct, 2),
        "sharpe": round(m.sharpe_annual, 2),
    }


def _by_year(trades: list[Trade], starting_equity: float) -> dict[int, dict]:
    if not trades:
        return {}
    by_year: dict[int, list[Trade]] = defaultdict(list)
    for t in trades:
        by_year[t.entry_time.year].append(t)
    out: dict[int, dict] = {}
    for year, ts in sorted(by_year.items()):
        n = len(ts)
        wins = [t for t in ts if t.pnl > 0]
        losses = [t for t in ts if t.pnl < 0]
        pnl = sum(t.pnl for t in ts)
        gains = sum(t.pnl for t in wins)
        loss = -sum(t.pnl for t in losses)
        pf = (gains / loss) if loss > 0 else float("inf") if gains > 0 else 0.0
        out[year] = {
            "trades": n,
            "win_rate": round(len(wins) / n, 4) if n else 0.0,
            "pf": round(pf, 2) if np.isfinite(pf) else None,
            "ret_pct_of_start_eq": round(pnl / starting_equity * 100.0, 2),
        }
    return out


def _mc_max_dd(trades: list[Trade], starting_equity: float, n_iter: int = 1000,
               seed: int = 0) -> dict:
    """Bootstrap the trade order and compute the distribution of max DD."""
    if not trades:
        return {"n": 0}
    rng = np.random.default_rng(seed)
    pnls = np.array([t.pnl for t in trades])
    n = len(pnls)
    dds = np.empty(n_iter, dtype=float)
    for k in range(n_iter):
        idx = rng.permutation(n)
        eq = starting_equity + np.cumsum(pnls[idx])
        peak = np.maximum.accumulate(eq)
        dds[k] = float(((eq - peak) / peak).min())
    return {
        "samples": n_iter,
        "median_dd_pct": round(float(np.median(dds)) * 100, 2),
        "p95_dd_pct": round(float(np.percentile(dds, 5)) * 100, 2),
        "p99_dd_pct": round(float(np.percentile(dds, 1)) * 100, 2),
        "worst_dd_pct": round(float(dds.min()) * 100, 2),
    }


def main() -> int:
    cache = {}
    for s in available_symbols():
        try:
            r = load_symbol(s, os.getcwd())
        except (FileNotFoundError, KeyError):
            continue
        setups = detect_setups(r.df, threshold_atr=3.0, atr_period=14, params=WaveParams())
        cache[s] = (r.df, setups)

    # Scenarios to test.
    scenarios = [
        ("frictionless",           dict(cost_per_trade=0.0, slippage_atr_mult=0.0)),
        ("realistic spread",       None),   # uses REALISTIC_COSTS per symbol
        ("strict spread",          None),   # uses STRICT_COSTS per symbol
        ("strict + 0.10xATR slip", None),
        ("strict + 0.20xATR slip", None),
        ("strict + 0.30xATR slip", None),
    ]

    all_rows = []
    print(f"{'scenario':<28} {'sym':<7} {'#tr':>4} {'win%':>5} {'PF':>6} "
          f"{'E[R]':>5} {'ret%':>8} {'DD%':>6} {'Shp':>5}")

    # Map scenario index -> overrides per symbol
    for label, fixed in scenarios:
        for sym, (df, setups) in cache.items():
            if label == "frictionless":
                ov = dict(fixed)
            elif label == "realistic spread":
                ov = dict(cost_per_trade=REALISTIC_COSTS.get(sym, 0.0), slippage_atr_mult=0.0)
            elif label == "strict spread":
                ov = dict(cost_per_trade=STRICT_COSTS.get(sym, 0.0), slippage_atr_mult=0.0)
            elif label == "strict + 0.10xATR slip":
                ov = dict(cost_per_trade=STRICT_COSTS.get(sym, 0.0), slippage_atr_mult=0.10)
            elif label == "strict + 0.20xATR slip":
                ov = dict(cost_per_trade=STRICT_COSTS.get(sym, 0.0), slippage_atr_mult=0.20)
            elif label == "strict + 0.30xATR slip":
                ov = dict(cost_per_trade=STRICT_COSTS.get(sym, 0.0), slippage_atr_mult=0.30)
            res = _run(df, setups, **ov)
            row = _row(sym, label, res, 10_000.0)
            all_rows.append(row)
            pf_str = f"{row['pf']:>5.2f}" if row['pf'] is not None else "  inf"
            print(f"{label:<28} {sym:<7} {row['trades']:>4} {row['win']*100:>4.1f}% "
                  f"{pf_str} {row['exp_r']:>+5.2f} {row['ret_pct']:>+8.2f} "
                  f"{row['dd_pct']:>+6.2f} {row['sharpe']:>+5.2f}")

    # Per-scenario portfolio aggregates.
    print("\nPortfolio average per scenario:")
    portfolio = []
    for label, _ in scenarios:
        rows = [r for r in all_rows if r["scenario"] == label]
        finite_pf = [r["pf"] for r in rows if r["pf"] is not None]
        agg = {
            "scenario": label,
            "mean_win": round(mean(r["win"] for r in rows), 4),
            "mean_pf": round(mean(finite_pf), 2) if finite_pf else None,
            "mean_exp_r": round(mean(r["exp_r"] for r in rows), 3),
            "mean_ret_pct": round(mean(r["ret_pct"] for r in rows), 2),
            "mean_dd_pct": round(mean(r["dd_pct"] for r in rows), 2),
            "mean_sharpe": round(mean(r["sharpe"] for r in rows), 2),
            "total_trades": sum(r["trades"] for r in rows),
        }
        portfolio.append(agg)
        print(f"  {label:<28}  trades={agg['total_trades']:>5}  "
              f"win={agg['mean_win']*100:5.1f}%  "
              f"PF={agg['mean_pf'] if agg['mean_pf'] is not None else 'inf':>5}  "
              f"E[R]={agg['mean_exp_r']:+5.2f}  ret={agg['mean_ret_pct']:+7.2f}%  "
              f"DD={agg['mean_dd_pct']:+6.2f}%  Sharpe={agg['mean_sharpe']:+5.2f}")

    # Year-by-year breakdown under the toughest scenario.
    print("\nYear-by-year under 'strict + 0.30xATR slip':")
    yearly_rows = {}
    for sym, (df, setups) in cache.items():
        ov = dict(cost_per_trade=STRICT_COSTS.get(sym, 0.0), slippage_atr_mult=0.30)
        res = _run(df, setups, **ov)
        yearly_rows[sym] = _by_year(res.trades, 10_000.0)
    years = sorted({y for v in yearly_rows.values() for y in v})
    header = "year   " + "  ".join(f"{s:<6}" for s in yearly_rows)
    print(header)
    for y in years:
        line = f"{y}   "
        for s in yearly_rows:
            v = yearly_rows[s].get(y)
            line += f"{(v['ret_pct_of_start_eq'] if v else 0.0):>+6.1f}  "
        print(line)

    # Monte Carlo DD bootstrap under toughest scenario.
    print("\nMonte Carlo trade-shuffle Max-DD (1000 perms, toughest scenario):")
    mc_rows = {}
    for sym, (df, setups) in cache.items():
        ov = dict(cost_per_trade=STRICT_COSTS.get(sym, 0.0), slippage_atr_mult=0.30)
        res = _run(df, setups, **ov)
        mc = _mc_max_dd(res.trades, 10_000.0)
        mc_rows[sym] = mc
        print(f"  {sym:<7}  median={mc.get('median_dd_pct',0):>+6.2f}%  "
              f"p95={mc.get('p95_dd_pct',0):>+6.2f}%  "
              f"p99={mc.get('p99_dd_pct',0):>+6.2f}%  "
              f"worst={mc.get('worst_dd_pct',0):>+6.2f}%")

    # Risk-per-trade sensitivity (compound mode, toughest scenario).
    print("\nRisk-per-trade sensitivity (compound mode, toughest scenario):")
    risk_rows = []
    for risk in (0.01, 0.02, 0.03, 0.05):
        finals = []
        dds = []
        for sym, (df, setups) in cache.items():
            ov = dict(
                cost_per_trade=STRICT_COSTS.get(sym, 0.0),
                slippage_atr_mult=0.30,
            )
            cfg = BacktestConfig(
                fixed_sizing=False, risk_per_trade=risk, **TUNED_EXIT, **ov,
            )
            res = run_backtest(df, setups, cfg)
            m = compute(res, cfg.starting_equity)
            finals.append(m.total_return_pct)
            dds.append(m.max_drawdown_pct)
        avg_ret = round(mean(finals), 2)
        avg_dd = round(mean(dds), 2)
        risk_rows.append({"risk": risk, "mean_ret_pct": avg_ret, "mean_dd_pct": avg_dd})
        print(f"  risk={risk*100:>4.1f}%  mean ret = {avg_ret:>+9.2f}%   mean DD = {avg_dd:>+7.2f}%")

    out = "elliott45/results/stress.json"
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w") as f:
        json.dump({
            "scenarios": all_rows,
            "portfolio": portfolio,
            "yearly_toughest": {s: {str(k): v for k, v in d.items()} for s, d in yearly_rows.items()},
            "mc_dd_toughest": mc_rows,
            "risk_sensitivity_toughest": risk_rows,
        }, f, indent=2)
    print(f"\nWritten {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
