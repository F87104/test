"""Matplotlib charts: price + levels + signals, equity curve, drawdown.

All functions are headless-safe (use the ``Agg`` backend) so they work in
cloud / SSH environments without a display.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import matplotlib

matplotlib.use("Agg")  # noqa: E402
import matplotlib.dates as mdates  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from .logger import get_logger

log = get_logger("trendbreak.plotter")


# ---------------------------------------------------------------------------
def plot_price_with_levels(
    indicator_df: pd.DataFrame,
    trades: pd.DataFrame,
    *,
    title: str,
    out_path: str | Path,
    max_bars: int = 6000,
) -> Path:
    df = indicator_df.tail(max_bars).copy()
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    fig, ax = plt.subplots(figsize=(15, 7))
    ax.plot(df.index, df["close"], color="#222", linewidth=0.8, label="close")
    ax.plot(df.index, df["highLevel"], color="#21a366", linewidth=1.2, label="highLevel(long)")
    ax.plot(df.index, df["lowLevel"], color="#d23f31", linewidth=1.2, label="lowLevel(long)")
    if "highLevel3m" in df.columns:
        ax.plot(df.index, df["highLevel3m"], color="#e3b505", linewidth=0.8, label="highLevel(mid)")
        ax.plot(df.index, df["lowLevel3m"], color="#c4006b", linewidth=0.8, label="lowLevel(mid)")
    if "midMedian3m" in df.columns:
        ax.plot(df.index, df["midMedian3m"], color="#2195f3", linewidth=0.6, alpha=0.6, label="mid median")

    if trades is not None and not trades.empty:
        in_window = trades[
            (trades["entry_time"] >= df.index[0]) & (trades["entry_time"] <= df.index[-1])
        ]
        longs = in_window[in_window["direction"] == "long"]
        shorts = in_window[in_window["direction"] == "short"]
        if not longs.empty:
            ax.scatter(
                longs["entry_time"], longs["entry_price"],
                marker="^", color="#21a366", s=40, label="long entry", zorder=5,
            )
        if not shorts.empty:
            ax.scatter(
                shorts["entry_time"], shorts["entry_price"],
                marker="v", color="#d23f31", s=40, label="short entry", zorder=5,
            )

    ax.set_title(title)
    ax.set_xlabel("time")
    ax.set_ylabel("price")
    ax.grid(True, alpha=0.3)
    ax.legend(loc="best", fontsize=8)
    ax.xaxis.set_major_locator(mdates.AutoDateLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d"))
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(out_path, dpi=120)
    plt.close(fig)
    log.info("price chart saved → %s", out_path)
    return out_path


# ---------------------------------------------------------------------------
def plot_equity_and_drawdown(
    equity: pd.Series,
    *,
    title: str,
    out_path: str | Path,
) -> Path:
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig, axes = plt.subplots(2, 1, figsize=(14, 7), sharex=True, gridspec_kw={"height_ratios": [3, 1]})

    if equity.empty:
        axes[0].text(0.5, 0.5, "no data", ha="center", va="center")
    else:
        axes[0].plot(equity.index, equity.values, color="#1a73e8", linewidth=1.2, label="equity")
        cummax = equity.cummax()
        axes[0].plot(equity.index, cummax.values, color="#aaaaaa", linewidth=0.8, linestyle="--", label="hwm")
        dd = (equity - cummax) / cummax.replace(0, np.nan)
        axes[1].fill_between(equity.index, dd.values, 0, color="#d23f31", alpha=0.4)
        axes[1].set_ylabel("DD %")

    axes[0].set_title(title)
    axes[0].set_ylabel("equity")
    axes[0].grid(True, alpha=0.3)
    axes[0].legend(loc="best", fontsize=8)
    axes[1].grid(True, alpha=0.3)
    axes[1].xaxis.set_major_locator(mdates.AutoDateLocator())
    axes[1].xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d"))
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(out_path, dpi=120)
    plt.close(fig)
    log.info("equity chart saved → %s", out_path)
    return out_path


# ---------------------------------------------------------------------------
def plot_distribution(
    trades: pd.DataFrame,
    *,
    title: str,
    out_path: str | Path,
) -> Optional[Path]:
    if trades is None or trades.empty:
        return None
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig, axes = plt.subplots(1, 2, figsize=(13, 4))
    axes[0].hist(trades["r_multiple"], bins=40, color="#1a73e8", alpha=0.8)
    axes[0].axvline(0, color="#222", linewidth=0.8)
    axes[0].set_title(f"{title} — R multiple distribution")
    axes[0].set_xlabel("R multiple")

    cum = trades["pnl_money"].cumsum()
    axes[1].plot(cum.values, color="#21a366")
    axes[1].set_title(f"{title} — cumulative PnL by trade #")
    axes[1].set_xlabel("trade #")
    axes[1].set_ylabel("cumulative PnL")
    axes[1].grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(out_path, dpi=120)
    plt.close(fig)
    log.info("distribution chart saved → %s", out_path)
    return out_path


__all__ = [
    "plot_price_with_levels",
    "plot_equity_and_drawdown",
    "plot_distribution",
]
