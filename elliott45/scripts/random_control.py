"""Sanity control: replace Elliott-Wave entries with PURELY RANDOM
entries that share the same SL/TP/trigger geometry. Then run the same
exit mechanics (partial + BE + trail). 

If the random-entry strategy also produces 80-90% win rates and high PF,
then the impressive numbers we see for the Elliott strategy are an
artefact of the exit logic, NOT a real edge.

If the random strategy is roughly break-even (~50% or worse, PF~1) while
Elliott stays at 80-90% / PF >> 1, the edge is real.
"""

from __future__ import annotations

import os
import sys
from statistics import mean

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import numpy as np  # noqa: E402

from elliott45.src.backtest import BacktestConfig, run_backtest  # noqa: E402
from elliott45.src.data_loader import available_symbols, load_symbol  # noqa: E402
from elliott45.src.elliott import Setup, WaveParams, detect_setups  # noqa: E402
from elliott45.src.metrics import compute  # noqa: E402
from elliott45.src.zigzag import Pivot, atr as atr_series_fn  # noqa: E402


def _make_random_setups(df, n_setups: int, seed: int = 0,
                        atr_period: int = 14) -> list[Setup]:
    """Generate n random setups whose SL/TP/trigger distances are drawn
    from the same ATR-scaled distribution as a real Elliott setup."""
    rng = np.random.default_rng(seed)
    atr = atr_series_fn(df, atr_period).to_numpy()
    close = df["close"].to_numpy()
    n = len(df)
    valid = np.where(~np.isnan(atr) & (atr > 0))[0]
    valid = valid[(valid > atr_period + 10) & (valid < n - 50)]
    if len(valid) == 0:
        return []
    chosen = rng.choice(valid, size=min(n_setups, len(valid)), replace=False)
    chosen = np.sort(chosen)
    out: list[Setup] = []
    for idx in chosen:
        direction = "long" if rng.random() < 0.5 else "short"
        a = atr[idx]
        # Match the Elliott setup geometry on average:
        #   risk  = 0.7 x W4 ≈ 0.7 x 4xATR = 2.8 x ATR
        #   reward= 1.0 x W1 − 0.2 x W4    ≈ a few ATR
        risk = max(2.0 * a, 1e-6)
        reward_mult = 1.0 + 0.5 * rng.random()  # 1.0 to 1.5 R
        ref = float(close[idx])
        if direction == "long":
            trigger = ref + 0.1 * a
            stop = trigger - risk
            target = trigger + reward_mult * risk
        else:
            trigger = ref - 0.1 * a
            stop = trigger + risk
            target = trigger - reward_mult * risk
        # Build a Setup wrapping fake pivots so the existing engine accepts it.
        p4 = Pivot(idx=int(idx), confirm_idx=int(idx), price=ref, kind="L" if direction == "long" else "H")
        ph = Pivot(idx=int(idx) - 5, confirm_idx=int(idx) - 4, price=ref + a, kind="H")
        pl = Pivot(idx=int(idx) - 10, confirm_idx=int(idx) - 9, price=ref - a, kind="L")
        out.append(
            Setup(
                direction=direction,
                p0=pl, p1=ph, p2=pl, p3=ph, p4=p4,
                w1_len=2 * a, w3_len=3 * a, w2_retrace=0.5, w4_retrace=0.5,
                entry_bar=int(idx) + 1,
                entry_ref_price=ref,
                trigger_price=float(trigger),
                stop_price=float(stop),
                target_price=float(target),
            )
        )
    return out


def main() -> int:
    print(f"{'symbol':<8} {'engine':<12} {'#tr':>5} {'win%':>6} "
          f"{'PF':>6} {'E[R]':>6} {'ret%':>8} {'DD%':>6} {'Sh':>5}")
    summary = {"elliott": [], "random": []}
    for sym in available_symbols():
        try:
            r = load_symbol(sym, os.getcwd())
        except (FileNotFoundError, KeyError):
            continue
        df = r.df

        # 1) Real Elliott setups under the tuned exit.
        ell_setups = detect_setups(df, threshold_atr=3.0, atr_period=14, params=WaveParams())
        cfg = BacktestConfig(
            fixed_sizing=True, partial_tp_r=1.0, partial_tp_size=0.5,
            move_be_at_partial=True, trail_atr_mult=2.0,
        )
        res = run_backtest(df, ell_setups, cfg)
        m = compute(res, cfg.starting_equity)
        summary["elliott"].append((sym, m))
        pf_str = f"{m.profit_factor:>5.2f}" if np.isfinite(m.profit_factor) else "  inf"
        print(f"{sym:<8} {'elliott':<12} {m.trades:>5} {m.win_rate*100:>5.1f}% "
              f"{pf_str} {m.expectancy_r:>+5.2f} {m.total_return_pct:>+8.2f} "
              f"{m.max_drawdown_pct:>+6.2f} {m.sharpe_annual:>+5.2f}")

        # 2) Random setups with matched geometry + the SAME exit mechanics.
        rnd_setups = _make_random_setups(df, n_setups=len(ell_setups), seed=42)
        res_r = run_backtest(df, rnd_setups, cfg)
        m_r = compute(res_r, cfg.starting_equity)
        summary["random"].append((sym, m_r))
        pf_str = f"{m_r.profit_factor:>5.2f}" if np.isfinite(m_r.profit_factor) else "  inf"
        print(f"{sym:<8} {'RANDOM':<12} {m_r.trades:>5} {m_r.win_rate*100:>5.1f}% "
              f"{pf_str} {m_r.expectancy_r:>+5.2f} {m_r.total_return_pct:>+8.2f} "
              f"{m_r.max_drawdown_pct:>+6.2f} {m_r.sharpe_annual:>+5.2f}")

    print("\nPortfolio averages:")
    for engine in ("elliott", "random"):
        wins = [m.win_rate for _, m in summary[engine] if m.trades]
        pfs = [m.profit_factor for _, m in summary[engine] if np.isfinite(m.profit_factor)]
        exp = [m.expectancy_r for _, m in summary[engine] if m.trades]
        rets = [m.total_return_pct for _, m in summary[engine]]
        dds = [m.max_drawdown_pct for _, m in summary[engine]]
        shs = [m.sharpe_annual for _, m in summary[engine]]
        print(f"  {engine:<8}  win={mean(wins)*100:5.1f}%  "
              f"PF={mean(pfs):>5.2f}  E[R]={mean(exp):+5.2f}  "
              f"ret={mean(rets):+7.2f}%  DD={mean(dds):+6.2f}%  "
              f"Sharpe={mean(shs):+5.2f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
