"""Performance metrics for backtest results."""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Optional

import numpy as np
import pandas as pd


@dataclass
class Metrics:
    n_trades: int
    n_long: int
    n_short: int
    win_rate: float
    long_win_rate: float
    short_win_rate: float
    profit_factor: float
    expectancy_r: float
    expectancy_money: float
    avg_win_r: float
    avg_loss_r: float
    avg_rr_realised: float
    max_drawdown_pct: float
    max_drawdown_money: float
    max_drawdown_duration_bars: int
    cagr: float
    sharpe: float
    sortino: float
    calmar: float
    total_return_pct: float
    avg_bars_held: float
    median_bars_held: float
    fakeout_rate: float

    def to_dict(self) -> dict:
        return asdict(self)


# ---------------------------------------------------------------------------
def _profit_factor(pnl: np.ndarray) -> float:
    profits = pnl[pnl > 0].sum()
    losses = -pnl[pnl < 0].sum()
    if losses == 0:
        return float("inf") if profits > 0 else 0.0
    return float(profits / losses)


def _max_drawdown(equity: pd.Series) -> tuple[float, float, int]:
    """Return (max_dd_pct, max_dd_money, dd_duration_bars)."""
    if equity.empty:
        return 0.0, 0.0, 0
    cummax = equity.cummax()
    dd = equity - cummax
    dd_pct = dd / cummax.replace(0, np.nan)
    max_dd_money = float(dd.min())
    max_dd_pct = float(dd_pct.min()) if dd_pct.notna().any() else 0.0
    # Duration: longest stretch where equity < running max
    in_dd = (equity < cummax).astype(int).to_numpy()
    longest = current = 0
    for v in in_dd:
        if v:
            current += 1
            longest = max(longest, current)
        else:
            current = 0
    return max_dd_pct, max_dd_money, longest


def _cagr(equity: pd.Series) -> float:
    if equity.empty or equity.iloc[0] <= 0:
        return 0.0
    duration_days = (equity.index[-1] - equity.index[0]).total_seconds() / 86400.0
    if duration_days <= 0:
        return 0.0
    years = duration_days / 365.25
    if years <= 0:
        return 0.0
    return float((equity.iloc[-1] / equity.iloc[0]) ** (1.0 / years) - 1.0)


def _sharpe_sortino(equity: pd.Series) -> tuple[float, float]:
    if len(equity) < 3:
        return 0.0, 0.0
    rets = equity.pct_change().dropna()
    if rets.std() == 0 or len(rets) < 2:
        return 0.0, 0.0
    # Frequency-aware annualisation
    median_dt = rets.index.to_series().diff().median()
    if pd.isna(median_dt) or median_dt.total_seconds() <= 0:
        ann = 252.0
    else:
        ann = (365.25 * 86400.0) / median_dt.total_seconds()
    sharpe = float(rets.mean() / rets.std() * np.sqrt(ann))
    downside = rets[rets < 0]
    if len(downside) < 2 or downside.std() == 0:
        sortino = 0.0
    else:
        sortino = float(rets.mean() / downside.std() * np.sqrt(ann))
    return sharpe, sortino


# ---------------------------------------------------------------------------
def compute_metrics(
    trades_df: pd.DataFrame, equity: pd.Series, *, initial_equity: Optional[float] = None
) -> Metrics:
    if trades_df is None or trades_df.empty:
        return Metrics(
            n_trades=0,
            n_long=0,
            n_short=0,
            win_rate=0.0,
            long_win_rate=0.0,
            short_win_rate=0.0,
            profit_factor=0.0,
            expectancy_r=0.0,
            expectancy_money=0.0,
            avg_win_r=0.0,
            avg_loss_r=0.0,
            avg_rr_realised=0.0,
            max_drawdown_pct=0.0,
            max_drawdown_money=0.0,
            max_drawdown_duration_bars=0,
            cagr=0.0,
            sharpe=0.0,
            sortino=0.0,
            calmar=0.0,
            total_return_pct=0.0,
            avg_bars_held=0.0,
            median_bars_held=0.0,
            fakeout_rate=0.0,
        )

    pnl_money = trades_df["pnl_money"].to_numpy()
    r = trades_df["r_multiple"].to_numpy()
    bars = trades_df["bars_held"].to_numpy()

    n = len(trades_df)
    long_mask = trades_df["direction"] == "long"
    n_long = int(long_mask.sum())
    n_short = int((~long_mask).sum())

    wins = pnl_money > 0
    win_rate = float(wins.mean())
    long_wr = (
        float(wins[long_mask].mean()) if n_long else 0.0
    )
    short_wr = (
        float(wins[~long_mask].mean()) if n_short else 0.0
    )
    pf = _profit_factor(pnl_money)
    avg_win_r = float(r[r > 0].mean()) if (r > 0).any() else 0.0
    avg_loss_r = float(r[r < 0].mean()) if (r < 0).any() else 0.0
    expectancy_r = float(r.mean())
    expectancy_money = float(pnl_money.mean())
    avg_rr = avg_win_r / abs(avg_loss_r) if avg_loss_r != 0 else 0.0

    if not equity.empty:
        if initial_equity is None or initial_equity <= 0:
            initial_equity = float(equity.iloc[0])
        if initial_equity <= 0:
            initial_equity = 1.0
        total_ret = float((equity.iloc[-1] / initial_equity - 1.0))
    else:
        total_ret = 0.0

    dd_pct, dd_money, dd_dur = _max_drawdown(equity) if not equity.empty else (0.0, 0.0, 0)
    cagr = _cagr(equity) if not equity.empty else 0.0
    sharpe, sortino = _sharpe_sortino(equity) if not equity.empty else (0.0, 0.0)
    calmar = cagr / abs(dd_pct) if dd_pct < 0 else 0.0

    return Metrics(
        n_trades=n,
        n_long=n_long,
        n_short=n_short,
        win_rate=win_rate,
        long_win_rate=long_wr,
        short_win_rate=short_wr,
        profit_factor=pf,
        expectancy_r=expectancy_r,
        expectancy_money=expectancy_money,
        avg_win_r=avg_win_r,
        avg_loss_r=avg_loss_r,
        avg_rr_realised=avg_rr,
        max_drawdown_pct=dd_pct,
        max_drawdown_money=dd_money,
        max_drawdown_duration_bars=dd_dur,
        cagr=cagr,
        sharpe=sharpe,
        sortino=sortino,
        calmar=calmar,
        total_return_pct=total_ret,
        avg_bars_held=float(np.mean(bars)),
        median_bars_held=float(np.median(bars)),
        fakeout_rate=float(trades_df["is_fakeout"].mean()) if "is_fakeout" in trades_df else 0.0,
    )


__all__ = ["Metrics", "compute_metrics"]
