"""Semi-automatic signal scanner.

Given a watch list of (symbol, data_dir, config_file), this module:

1. Loads the latest OHLCV history for each symbol
2. Runs the Pine-equivalent indicator with the symbol's optimised config
3. Scans the most recent ``lookback_bars`` and reports every fired signal
4. For each signal, computes ALL the information a discretionary trader needs
   to place the order manually: entry price, SL, TP, R risk, position size,
   account-currency loss, expected R, session, weekday, etc.

Pure read-only — never touches a broker.  You use this to *get told* "an
XAUUSD long signal fired on 2025-07-06 22:00 UTC, here are the exact prices
to use" and you place the trade yourself.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

from .backtest import _apply_pretrade_filters, _classify_session, _compute_sl_tp, _signal_series
from .config import BacktestConfig, FullConfig, IndicatorConfig
from .data_loader import infer_pip_size, load_csvs
from .indicator import atr, compute_indicator
from .logger import get_logger

log = get_logger("trendbreak.signals")


# ---------------------------------------------------------------------------
@dataclass
class Signal:
    symbol: str
    direction: str                  # 'long' | 'short'
    level_kind: str                 # 'long' | 'mid' | 'confluence'
    signal_time: pd.Timestamp       # UTC
    signal_close: float
    level_price: float              # the level that was broken
    margin_atr: float               # (close − level) / ATR  (strength)

    proposed_entry_price: float     # exec at next bar open by default
    proposed_sl: float
    proposed_tp: Optional[float]
    risk_per_unit: float
    reward_per_unit: Optional[float]
    rr_ratio: Optional[float]
    atr_at_signal: float

    session: str                    # 'asia' | 'europe' | 'ny'
    weekday: str
    hour_utc: int

    # Strategy meta-data
    config_label: str
    config_path: Optional[str]
    expected_r: float               # = tp_rr if rr mode

    # Sizing helper (account currency)
    account_equity: float
    risk_pct: float
    risk_money: float
    suggested_size_units: float
    pip_size: float
    suggested_size_lots: float      # for 100 oz / 100K FX standard lot

    # Backtest reference (for context)
    backtest_pf: Optional[float] = None
    backtest_win_rate: Optional[float] = None

    bars_since_signal: int = 0      # 0 = freshest

    def to_dict(self) -> dict:
        d = asdict(self)
        d["signal_time"] = self.signal_time.isoformat()
        return d


@dataclass
class WatchItem:
    symbol: str
    data_dir: str                   # path to a folder of yearly CSVs
    config_path: Optional[str] = None  # JSON config; if None use defaults
    pip_size: Optional[float] = None

    @classmethod
    def from_dict(cls, d: dict) -> "WatchItem":
        return cls(
            symbol=d["symbol"],
            data_dir=d["data_dir"],
            config_path=d.get("config_path"),
            pip_size=d.get("pip_size"),
        )


# ---------------------------------------------------------------------------
def _load_full_cfg(cfg_path: Optional[str | Path]) -> FullConfig:
    if cfg_path is None:
        return FullConfig()
    with open(cfg_path, "r", encoding="utf-8") as f:
        return FullConfig.from_dict(json.load(f))


def scan_symbol(
    item: WatchItem,
    *,
    lookback_bars: int = 240,
    backtest_pf: Optional[float] = None,
    backtest_win_rate: Optional[float] = None,
) -> tuple[Optional[Signal], list[Signal]]:
    """Return (freshest_signal, recent_signals).

    The freshest signal is the one whose ``signal_time`` is the most recent.
    ``recent_signals`` lists every fired signal within the last
    ``lookback_bars`` (sorted newest → oldest).
    """
    cfg = _load_full_cfg(item.config_path)
    icfg = cfg.indicator
    bcfg = cfg.backtest

    files = sorted(Path(item.data_dir).rglob("*.csv"))
    if not files:
        raise FileNotFoundError(f"[ERR-IO] no CSVs under {item.data_dir}")
    df, _ = load_csvs(files, timezone=cfg.run.timezone)
    if len(df) < icfg.lookback_3m + 50:
        raise ValueError(
            f"[ERR-DATA] {item.symbol}: only {len(df)} rows, need at least "
            f"{icfg.lookback_3m + 50}"
        )

    res = compute_indicator(df, icfg)
    out_df = res.df
    long_arr, short_arr = _signal_series(res, bcfg.level_kind, bcfg.direction)
    atr_series = atr(df, period=bcfg.atr_period).to_numpy()

    # Apply pre-trade filters identical to backtest
    long_arr, short_arr = _apply_pretrade_filters(
        df=df, out_df=out_df, long_arr=long_arr, short_arr=short_arr,
        atr_series=atr_series, backtest_cfg=bcfg,
    )

    pip_size = item.pip_size if item.pip_size is not None else infer_pip_size(item.symbol)
    n = len(df)
    start = max(0, n - lookback_bars)
    signals: list[Signal] = []
    for t in range(start, n):
        if long_arr[t]:
            sig = _build_signal(
                t=t, df=df, out_df=out_df, atr_series=atr_series,
                direction=1, icfg=icfg, bcfg=bcfg, item=item, pip_size=pip_size,
                config_label=Path(item.config_path).stem if item.config_path else "default",
                backtest_pf=backtest_pf, backtest_win_rate=backtest_win_rate,
                bars_since=n - 1 - t,
            )
            signals.append(sig)
        elif short_arr[t]:
            sig = _build_signal(
                t=t, df=df, out_df=out_df, atr_series=atr_series,
                direction=-1, icfg=icfg, bcfg=bcfg, item=item, pip_size=pip_size,
                config_label=Path(item.config_path).stem if item.config_path else "default",
                backtest_pf=backtest_pf, backtest_win_rate=backtest_win_rate,
                bars_since=n - 1 - t,
            )
            signals.append(sig)
    signals.sort(key=lambda s: s.signal_time, reverse=True)
    return (signals[0] if signals else None), signals


def _build_signal(
    *,
    t: int,
    df: pd.DataFrame,
    out_df: pd.DataFrame,
    atr_series: np.ndarray,
    direction: int,
    icfg: IndicatorConfig,
    bcfg: BacktestConfig,
    item: WatchItem,
    pip_size: float,
    config_label: str,
    backtest_pf: Optional[float],
    backtest_win_rate: Optional[float],
    bars_since: int,
) -> Signal:
    times = df.index
    high = df["high"].to_numpy()
    low = df["low"].to_numpy()
    close = df["close"].to_numpy()
    open_ = df["open"].to_numpy()

    if bcfg.level_kind in ("long", "confluence"):
        level_col_h = "highLevel"
        level_col_l = "lowLevel"
    else:
        level_col_h = "highLevel3m"
        level_col_l = "lowLevel3m"
    level_h = float(out_df[level_col_h].iloc[t])
    level_l = float(out_df[level_col_l].iloc[t])
    sig_close = float(close[t])
    atr_t = float(atr_series[t]) if not np.isnan(atr_series[t]) else 0.0

    # Proposed entry assumes next_open fill at signal_close as a *guidance*.
    # When the bar that fires the signal is the LAST bar, no next_open exists
    # yet — the user will see the actual fill when the next bar opens.
    entry_px = sig_close  # best estimate; real fill = next open
    sl, tp = _compute_sl_tp(
        cfg=bcfg, direction=direction, entry_price=entry_px,
        atr_value=atr_t, signal_bar_high=float(high[t]), signal_bar_low=float(low[t]),
    )
    risk_per_unit = abs(entry_px - sl)
    reward_per_unit = abs(tp - entry_px) if tp is not None else None
    rr_ratio = (reward_per_unit / risk_per_unit) if (reward_per_unit and risk_per_unit) else None
    margin_atr = (
        (sig_close - level_h) / atr_t if direction == 1 and atr_t > 0
        else (level_l - sig_close) / atr_t if direction == -1 and atr_t > 0
        else 0.0
    )

    # Sizing
    risk_money = bcfg.initial_equity * (bcfg.risk_per_trade_pct / 100.0)
    size_units = (risk_money / max(risk_per_unit, 1e-12))
    # Standard lot for FX = 100,000 units; for XAUUSD = 100 oz; XAGUSD = 5,000 oz.
    # We approximate by 100 oz for metals, 100K for FX
    sym = item.symbol.upper()
    lot_unit = 100.0 if sym.startswith(("XAU", "GOLD")) else (
        5000.0 if sym.startswith(("XAG", "SILVER")) else 100_000.0
    )
    size_lots = size_units / lot_unit

    entry_t: pd.Timestamp = times[t]
    return Signal(
        symbol=item.symbol,
        direction="long" if direction == 1 else "short",
        level_kind=bcfg.level_kind,
        signal_time=entry_t,
        signal_close=sig_close,
        level_price=level_h if direction == 1 else level_l,
        margin_atr=float(margin_atr),
        proposed_entry_price=entry_px,
        proposed_sl=sl,
        proposed_tp=tp,
        risk_per_unit=risk_per_unit,
        reward_per_unit=reward_per_unit,
        rr_ratio=rr_ratio,
        atr_at_signal=atr_t,
        session=_classify_session(int(entry_t.hour)),
        weekday=entry_t.strftime("%A"),
        hour_utc=int(entry_t.hour),
        config_label=config_label,
        config_path=item.config_path,
        expected_r=bcfg.tp_rr if bcfg.tp_mode == "rr" else 0.0,
        account_equity=bcfg.initial_equity,
        risk_pct=bcfg.risk_per_trade_pct,
        risk_money=risk_money,
        suggested_size_units=size_units,
        pip_size=pip_size,
        suggested_size_lots=size_lots,
        backtest_pf=backtest_pf,
        backtest_win_rate=backtest_win_rate,
        bars_since_signal=bars_since,
    )


# ---------------------------------------------------------------------------
def format_signal_human(s: Signal, *, fresh: bool = False) -> str:
    """Pretty-print a single signal for terminal output (Japanese)."""
    badge = "★★★ NEW ★★★" if fresh else f"  (発火後 {s.bars_since_signal} バー経過)"
    dir_jp = "🟢 ロング (買い)" if s.direction == "long" else "🔴 ショート (売り)"
    pf = f"PF {s.backtest_pf:.2f}" if s.backtest_pf is not None else "PF —"
    wr = f"WR {s.backtest_win_rate*100:.1f}%" if s.backtest_win_rate is not None else "WR —"

    lines = [
        "=" * 78,
        f"{badge}  |  {s.symbol}  |  {dir_jp}  |  {s.signal_time.strftime('%Y-%m-%d %H:%M UTC')}",
        "=" * 78,
        f"  水準 (level_kind={s.level_kind})    : {s.level_price:>14,.5f}",
        f"  シグナル終値 close             : {s.signal_close:>14,.5f}",
        f"  突破幅 / ATR (信号強度)        : {s.margin_atr:>14.3f}",
        f"  ATR(14)                       : {s.atr_at_signal:>14,.5f}",
        f"  時間帯                        : {s.session} / {s.weekday} / {s.hour_utc:02d}h UTC",
        "",
        "─ 【手動エントリー指示】 " + "─" * 50,
        f"  種別                          : 翌バー始値 (next_open)",
        f"  予想エントリー価格            : {s.proposed_entry_price:>14,.5f}",
        f"  ストップロス  SL              : {s.proposed_sl:>14,.5f}    "
        f"(損失幅 {s.risk_per_unit:.5f})",
    ]
    if s.proposed_tp is not None:
        lines.append(
            f"  テイクプロフィット TP         : {s.proposed_tp:>14,.5f}    "
            f"(利益幅 {s.reward_per_unit:.5f},  RR 1:{s.rr_ratio:.2f})"
        )
    else:
        lines.append("  テイクプロフィット TP         : なし (トレーリング想定)")
    lines += [
        "",
        "─ 【ポジションサイジング】 " + "─" * 47,
        f"  口座残高想定                  : ${s.account_equity:>11,.2f}",
        f"  1 トレードリスク (=1R)        : ${s.risk_money:>11,.2f}  ({s.risk_pct:.2f}%)",
        f"  推奨ユニット数                : {s.suggested_size_units:>11,.4f}",
        f"  推奨ロット数 (標準ロット換算) : {s.suggested_size_lots:>11,.4f}",
        f"  pip サイズ                    : {s.pip_size}",
        "",
        "─ 【期待値 (バックテスト基準)】 " + "─" * 43,
        f"  戦略                          : {s.config_label}",
        f"  バックテスト                  : {pf} / {wr}  / 期待 R: +{s.expected_r:.2f}",
        "=" * 78,
    ]
    return "\n".join(lines)


def format_signal_oneline(s: Signal, fresh: bool = False) -> str:
    """Compact one-line summary for tables."""
    flag = "★NEW" if fresh else f" +{s.bars_since_signal}b"
    dir_str = "LONG " if s.direction == "long" else "SHORT"
    return (
        f"{flag:>6}  {s.symbol:7s}  {dir_str}  "
        f"@{s.proposed_entry_price:>12,.4f}  "
        f"SL={s.proposed_sl:>12,.4f}  "
        f"TP={s.proposed_tp:>12,.4f}  "
        f"RR=1:{s.rr_ratio:>4.1f}  "
        f"{s.signal_time.strftime('%Y-%m-%d %H:%M')}  {s.session}"
        if s.proposed_tp is not None
        else (
            f"{flag:>6}  {s.symbol:7s}  {dir_str}  "
            f"@{s.proposed_entry_price:>12,.4f}  "
            f"SL={s.proposed_sl:>12,.4f}  TP=trail  "
            f"{s.signal_time.strftime('%Y-%m-%d %H:%M')}  {s.session}"
        )
    )


__all__ = [
    "Signal",
    "WatchItem",
    "scan_symbol",
    "format_signal_human",
    "format_signal_oneline",
]
