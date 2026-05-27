"""Performance metrics for the Elliott 4→5 backtester."""

from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np
import pandas as pd

from .backtest import BacktestResult, Trade


@dataclass
class Metrics:
    trades: int
    wins: int
    losses: int
    win_rate: float
    profit_factor: float
    expectancy_r: float
    avg_win_r: float
    avg_loss_r: float
    total_return_pct: float
    max_drawdown_pct: float
    sharpe_annual: float
    starting_equity: float
    ending_equity: float

    def as_dict(self) -> dict:
        return asdict(self)


def _profit_factor(trades: list[Trade]) -> float:
    gains = sum(t.pnl for t in trades if t.pnl > 0)
    losses = -sum(t.pnl for t in trades if t.pnl < 0)
    if losses == 0:
        return float("inf") if gains > 0 else 0.0
    return gains / losses


def _max_drawdown(equity: pd.Series) -> float:
    if equity.empty:
        return 0.0
    eq = equity.ffill().dropna()
    if eq.empty:
        return 0.0
    peak = eq.cummax()
    dd = (eq - peak) / peak
    return float(dd.min())


def _annualised_sharpe(equity: pd.Series, periods_per_year: float = 24 * 252) -> float:
    eq = equity.ffill().dropna()
    if len(eq) < 2:
        return 0.0
    rets = eq.pct_change().dropna()
    if rets.std() == 0:
        return 0.0
    return float(rets.mean() / rets.std() * np.sqrt(periods_per_year))


def compute(result: BacktestResult, starting_equity: float) -> Metrics:
    trades = result.trades
    wins = [t for t in trades if t.pnl > 0]
    losses = [t for t in trades if t.pnl < 0]
    n = len(trades)
    win_rate = (len(wins) / n) if n else 0.0
    pf = _profit_factor(trades)
    avg_win_r = float(np.mean([t.r_multiple for t in wins])) if wins else 0.0
    avg_loss_r = float(np.mean([t.r_multiple for t in losses])) if losses else 0.0
    expectancy = float(np.mean([t.r_multiple for t in trades])) if trades else 0.0
    ending = float(result.equity.dropna().iloc[-1]) if len(result.equity.dropna()) else starting_equity
    total_ret = (ending / starting_equity - 1.0) * 100.0
    dd = _max_drawdown(result.equity) * 100.0
    sharpe = _annualised_sharpe(result.equity)
    return Metrics(
        trades=n,
        wins=len(wins),
        losses=len(losses),
        win_rate=win_rate,
        profit_factor=pf,
        expectancy_r=expectancy,
        avg_win_r=avg_win_r,
        avg_loss_r=avg_loss_r,
        total_return_pct=total_ret,
        max_drawdown_pct=dd,
        sharpe_annual=sharpe,
        starting_equity=starting_equity,
        ending_equity=ending,
    )
