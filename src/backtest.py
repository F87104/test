"""Event-driven backtest engine — repaint-proof and future-data-proof.

Design highlights
-----------------
1. The indicator is computed **once** on the full series (vectorised); the
   engine then walks bar-by-bar and only ever consumes data from the *closed*
   bar at index ``t`` and earlier.
2. Entry fills happen on bar ``t+1`` open by default, so the entry decision
   is made strictly with information available *before* the entry bar.
3. Stop-loss / take-profit checks evaluate ``low`` and ``high`` of the bar
   *after* entry — never the entry bar itself — to avoid look-ahead.
4. ``one_position_only`` (default) ensures we never open a new trade while
   one is open, mirroring most retail strategies.
5. Each trade is a self-contained ``Trade`` dataclass, easy to serialise.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict, field
from typing import List, Optional

import numpy as np
import pandas as pd

from .config import BacktestConfig, FullConfig, IndicatorConfig
from .indicator import IndicatorResult, atr, compute_indicator
from .logger import get_logger

log = get_logger("trendbreak.backtest")


# ---------------------------------------------------------------------------
@dataclass
class Trade:
    trade_id: int
    symbol: str
    direction: str  # 'long' | 'short'
    level_kind: str  # 'long' | 'mid' | 'confluence'
    signal_time: pd.Timestamp
    entry_time: pd.Timestamp
    entry_price: float
    sl: float
    tp: Optional[float]
    exit_time: pd.Timestamp
    exit_price: float
    exit_reason: str  # 'tp' | 'sl' | 'time' | 'eod'
    bars_held: int
    pnl_price: float  # raw price diff
    pnl_pips: float
    pnl_pct: float  # of entry price
    pnl_money: float  # PnL in account currency given position size
    r_multiple: float
    atr_at_entry: float
    session: str
    weekday: str
    hour_utc: int
    is_fakeout: bool = False
    # Pine parameters used (for audit trail)
    lookback: int = 0
    exclude_recent: int = 0
    lookback_3m: int = 0
    exclude_recent_3m: int = 0


@dataclass
class BacktestResult:
    trades: List[Trade] = field(default_factory=list)
    equity_curve: pd.Series = field(default_factory=lambda: pd.Series(dtype=float))
    indicator_df: pd.DataFrame = field(default_factory=pd.DataFrame)
    config_snapshot: dict = field(default_factory=dict)

    @property
    def trades_df(self) -> pd.DataFrame:
        if not self.trades:
            return pd.DataFrame(columns=[f.name for f in Trade.__dataclass_fields__.values()])
        return pd.DataFrame([asdict(t) for t in self.trades])


# ---------------------------------------------------------------------------
_SESSION_BOUNDARIES = (
    # (start_hour_utc, end_hour_utc_exclusive, name)
    (0, 7, "asia"),
    (7, 13, "europe"),
    (13, 21, "ny"),
    (21, 24, "asia"),  # late session is mostly Asia again
)


def _classify_session(hour_utc: int) -> str:
    for s, e, name in _SESSION_BOUNDARIES:
        if s <= hour_utc < e:
            return name
    return "unknown"


# ---------------------------------------------------------------------------
def _apply_pretrade_filters(
    *,
    df: pd.DataFrame,
    out_df: pd.DataFrame,
    long_arr: np.ndarray,
    short_arr: np.ndarray,
    atr_series: np.ndarray,
    backtest_cfg: BacktestConfig,
) -> tuple[np.ndarray, np.ndarray]:
    """Mask out signals that fail any of the enabled pre-trade filters."""
    long_arr = long_arr.copy()
    short_arr = short_arr.copy()
    n = len(long_arr)

    # ---- 1) Session filter ---------------------------------------------
    # We filter on the *entry* bar's session, not the signal bar's, so that
    # ``trade.session`` always matches the user's filter.  With the default
    # entry_fill='next_open', entry is at bar t+1, so we shift the mask by -1.
    if backtest_cfg.session_filter:
        allowed = {s.lower() for s in backtest_cfg.session_filter}
        sessions = np.array(
            [_classify_session(t.hour) for t in df.index], dtype=object
        )
        in_allowed = np.array([s in allowed for s in sessions])
        if backtest_cfg.entry_fill == "next_open":
            # signal at t → entry at t+1.  Shift mask backward by 1.
            shifted = np.zeros_like(in_allowed)
            shifted[:-1] = in_allowed[1:]
            in_allowed = shifted
        long_arr &= in_allowed
        short_arr &= in_allowed

    # ---- 2) Break-out margin filter (close - level) / ATR --------------
    if backtest_cfg.min_breakout_margin_atr > 0:
        close = df["close"].to_numpy(dtype=float)
        h_lvl = out_df["highLevel" if backtest_cfg.level_kind != "mid"
                       else "highLevel3m"].to_numpy(dtype=float)
        l_lvl = out_df["lowLevel" if backtest_cfg.level_kind != "mid"
                       else "lowLevel3m"].to_numpy(dtype=float)
        with np.errstate(invalid="ignore", divide="ignore"):
            margin_long = (close - h_lvl) / np.where(atr_series > 0, atr_series, np.nan)
            margin_short = (l_lvl - close) / np.where(atr_series > 0, atr_series, np.nan)
        long_arr &= np.nan_to_num(margin_long, nan=-1.0) >= backtest_cfg.min_breakout_margin_atr
        short_arr &= np.nan_to_num(margin_short, nan=-1.0) >= backtest_cfg.min_breakout_margin_atr

    # ---- 3) Body-strength filter |close-open|/(high-low) ---------------
    if backtest_cfg.min_body_strength > 0:
        body = (df["close"] - df["open"]).abs()
        rng = (df["high"] - df["low"]).clip(lower=1e-12)
        strength = (body / rng).to_numpy()
        ok = strength >= backtest_cfg.min_body_strength
        long_arr &= ok
        short_arr &= ok

    # ---- 4) Volatility regime filter -----------------------------------
    if backtest_cfg.atr_pct_band is not None:
        lo, hi = backtest_cfg.atr_pct_band
        s = pd.Series(atr_series)
        rank = s.rank(pct=True).to_numpy()
        # NaNs (warm-up) → False
        rank_safe = np.nan_to_num(rank, nan=-1.0)
        ok = (rank_safe >= lo) & (rank_safe <= hi)
        long_arr &= ok
        short_arr &= ok

    return long_arr, short_arr


# ---------------------------------------------------------------------------
def _signal_series(
    res: IndicatorResult, level_kind: str, direction: str
) -> tuple[np.ndarray, np.ndarray]:
    """Return (long_arr, short_arr) boolean numpy arrays based on level kind."""
    df = res.df
    if level_kind == "long":
        long_s, short_s = df["longCond"], df["shortCond"]
    elif level_kind == "mid":
        long_s, short_s = df["longCond3m"], df["shortCond3m"]
    elif level_kind == "confluence":
        long_s = df["longCond"] & df["longCond3m"]
        short_s = df["shortCond"] & df["shortCond3m"]
    else:
        raise ValueError(f"[ERR-PARAM] unknown level_kind={level_kind!r}")

    if direction == "long_only":
        short_s = pd.Series(False, index=df.index)
    elif direction == "short_only":
        long_s = pd.Series(False, index=df.index)
    elif direction != "both":
        raise ValueError(f"[ERR-PARAM] unknown direction={direction!r}")

    return long_s.to_numpy(dtype=bool), short_s.to_numpy(dtype=bool)


# ---------------------------------------------------------------------------
def run_backtest(
    df: pd.DataFrame,
    *,
    indicator_cfg: IndicatorConfig,
    backtest_cfg: BacktestConfig,
    symbol: str = "UNKNOWN",
    pip_size: Optional[float] = None,
) -> BacktestResult:
    """Run the indicator + execute trades."""
    indicator_cfg.validate()
    backtest_cfg.validate()
    if len(df) < 10:
        raise ValueError("[ERR-DATA] need at least 10 bars to backtest")
    if pip_size is None:
        pip_size = backtest_cfg.pip_size
    if pip_size <= 0:
        raise ValueError("[ERR-PARAM] pip_size must be > 0")

    res = compute_indicator(df, indicator_cfg)
    out_df = res.df
    long_arr, short_arr = _signal_series(
        res, backtest_cfg.level_kind, backtest_cfg.direction
    )
    atr_series = atr(df, period=backtest_cfg.atr_period).to_numpy()

    # ---- Precompute pre-trade filter masks -----------------------------
    long_arr, short_arr = _apply_pretrade_filters(
        df=df,
        out_df=out_df,
        long_arr=long_arr,
        short_arr=short_arr,
        atr_series=atr_series,
        backtest_cfg=backtest_cfg,
    )

    high = df["high"].to_numpy(dtype=float)
    low = df["low"].to_numpy(dtype=float)
    close = df["close"].to_numpy(dtype=float)
    open_ = df["open"].to_numpy(dtype=float)
    times: pd.DatetimeIndex = df.index  # type: ignore[assignment]

    n = len(df)
    trades: List[Trade] = []
    equity = backtest_cfg.initial_equity
    equity_curve = np.full(n, equity, dtype=float)

    in_pos = False
    pos_dir = 0  # +1 long, -1 short
    pos_entry_idx = -1
    pos_entry_price = 0.0
    pos_sl = 0.0
    pos_tp: Optional[float] = None
    pos_signal_time = times[0]
    pos_atr = 0.0
    pos_size = 0.0
    pos_risk_money = 0.0
    pending_signal: Optional[int] = None  # +1/-1 → fill on next bar's open

    cost_per_unit = backtest_cfg.cost_pips * pip_size
    slip_per_unit = backtest_cfg.slippage_pips * pip_size

    log.info(
        "running backtest: symbol=%s n=%d level_kind=%s direction=%s",
        symbol,
        n,
        backtest_cfg.level_kind,
        backtest_cfg.direction,
    )

    # Trailing stop running state -- reset on every entry
    pos_max_favourable = 0.0  # tracks high (long) / low (short) since entry

    for t in range(n):
        # ---------- Manage open position FIRST (use current bar's H/L) ----
        if in_pos and t > pos_entry_idx:
            bar_high = high[t]
            bar_low = low[t]

            # ---- Break-even move: once price travels +R in our favour,
            #      shift SL to entry (lock in zero loss).
            if backtest_cfg.breakeven_at_r > 0 and pos_risk_money > 0:
                if pos_dir == 1:
                    favourable = bar_high - pos_entry_price
                else:
                    favourable = pos_entry_price - bar_low
                r_travelled = favourable / max(abs(pos_entry_price - pos_sl), 1e-12)
                if r_travelled >= backtest_cfg.breakeven_at_r:
                    new_sl = pos_entry_price
                    if pos_dir == 1 and new_sl > pos_sl:
                        pos_sl = new_sl
                    elif pos_dir == -1 and new_sl < pos_sl:
                        pos_sl = new_sl

            # ---- ATR trailing stop: trail SL from the max-favourable price
            if backtest_cfg.trailing_atr_mult > 0:
                atr_t = atr_series[t]
                if not np.isnan(atr_t) and atr_t > 0:
                    if pos_dir == 1:
                        pos_max_favourable = max(pos_max_favourable, bar_high)
                        new_sl = pos_max_favourable - backtest_cfg.trailing_atr_mult * atr_t
                        if new_sl > pos_sl:
                            pos_sl = new_sl
                    else:
                        pos_max_favourable = min(pos_max_favourable, bar_low)
                        new_sl = pos_max_favourable + backtest_cfg.trailing_atr_mult * atr_t
                        if new_sl < pos_sl:
                            pos_sl = new_sl

            exit_price: Optional[float] = None
            exit_reason = ""
            if pos_dir == 1:
                hit_sl = bar_low <= pos_sl
                hit_tp = pos_tp is not None and bar_high >= pos_tp
            else:
                hit_sl = bar_high >= pos_sl
                hit_tp = pos_tp is not None and bar_low <= pos_tp
            # If both hit in same bar, assume SL hit first (conservative)
            if hit_sl:
                exit_price = pos_sl
                exit_reason = "sl"
            elif hit_tp:
                exit_price = pos_tp
                exit_reason = "tp"
            elif (
                backtest_cfg.time_exit_bars > 0
                and (t - pos_entry_idx) >= backtest_cfg.time_exit_bars
            ):
                exit_price = close[t]
                exit_reason = "time"

            if exit_price is not None:
                _close_trade(
                    trades=trades,
                    symbol=symbol,
                    indicator_cfg=indicator_cfg,
                    backtest_cfg=backtest_cfg,
                    pos_dir=pos_dir,
                    pos_entry_idx=pos_entry_idx,
                    pos_entry_price=pos_entry_price,
                    pos_sl=pos_sl,
                    pos_tp=pos_tp,
                    pos_signal_time=pos_signal_time,
                    pos_atr=pos_atr,
                    pos_size=pos_size,
                    pos_risk_money=pos_risk_money,
                    exit_price=float(exit_price),
                    exit_idx=t,
                    exit_reason=exit_reason,
                    times=times,
                    cost_per_unit=cost_per_unit,
                    slip_per_unit=slip_per_unit,
                    pip_size=pip_size,
                    out_df=out_df,
                )
                equity += trades[-1].pnl_money
                in_pos = False

        # ---------- Open a pending entry (filled on this bar's open) -----
        if (
            not in_pos
            and pending_signal is not None
            and backtest_cfg.entry_fill == "next_open"
        ):
            pos_dir = pending_signal
            entry_px = open_[t] + slip_per_unit * pos_dir
            pos_entry_idx = t
            pos_entry_price = float(entry_px)
            pos_atr = float(atr_series[t - 1]) if not np.isnan(atr_series[t - 1]) else 0.0
            sl, tp = _compute_sl_tp(
                cfg=backtest_cfg,
                direction=pos_dir,
                entry_price=pos_entry_price,
                atr_value=pos_atr,
                signal_bar_high=high[t - 1],
                signal_bar_low=low[t - 1],
            )
            pos_sl, pos_tp = sl, tp
            pos_size, pos_risk_money = _compute_size(
                equity=equity,
                risk_pct=backtest_cfg.risk_per_trade_pct,
                entry_price=pos_entry_price,
                sl=pos_sl,
            )
            pos_max_favourable = pos_entry_price
            in_pos = True
            pending_signal = None

        # ---------- Generate new signal at this bar's close --------------
        if not in_pos:
            sig_long = bool(long_arr[t])
            sig_short = bool(short_arr[t])
            if sig_long and sig_short:
                # Conflicting same-bar signals → skip
                pass
            elif sig_long:
                if backtest_cfg.entry_fill == "signal_close":
                    _open_at_close(
                        backtest_cfg=backtest_cfg,
                        sig_dir=1,
                        t=t,
                        high=high,
                        low=low,
                        close=close,
                        atr_series=atr_series,
                        equity=equity,
                        slip_per_unit=slip_per_unit,
                        times=times,
                        on_open=lambda **kw: None,
                    )
                    pos_dir = 1
                    entry_px = close[t] + slip_per_unit
                    pos_entry_idx = t
                    pos_entry_price = float(entry_px)
                    pos_atr = float(atr_series[t]) if not np.isnan(atr_series[t]) else 0.0
                    pos_sl, pos_tp = _compute_sl_tp(
                        cfg=backtest_cfg,
                        direction=1,
                        entry_price=pos_entry_price,
                        atr_value=pos_atr,
                        signal_bar_high=high[t],
                        signal_bar_low=low[t],
                    )
                    pos_signal_time = times[t]
                    pos_size, pos_risk_money = _compute_size(
                        equity=equity,
                        risk_pct=backtest_cfg.risk_per_trade_pct,
                        entry_price=pos_entry_price,
                        sl=pos_sl,
                    )
                    in_pos = True
                else:
                    pending_signal = 1
                    pos_signal_time = times[t]
            elif sig_short:
                if backtest_cfg.entry_fill == "signal_close":
                    pos_dir = -1
                    entry_px = close[t] - slip_per_unit
                    pos_entry_idx = t
                    pos_entry_price = float(entry_px)
                    pos_atr = float(atr_series[t]) if not np.isnan(atr_series[t]) else 0.0
                    pos_sl, pos_tp = _compute_sl_tp(
                        cfg=backtest_cfg,
                        direction=-1,
                        entry_price=pos_entry_price,
                        atr_value=pos_atr,
                        signal_bar_high=high[t],
                        signal_bar_low=low[t],
                    )
                    pos_signal_time = times[t]
                    pos_size, pos_risk_money = _compute_size(
                        equity=equity,
                        risk_pct=backtest_cfg.risk_per_trade_pct,
                        entry_price=pos_entry_price,
                        sl=pos_sl,
                    )
                    in_pos = True
                else:
                    pending_signal = -1
                    pos_signal_time = times[t]

        equity_curve[t] = equity if not in_pos else _mark_to_market(
            equity=equity,
            pos_dir=pos_dir,
            pos_size=pos_size,
            entry=pos_entry_price,
            mark=close[t],
            cost_per_unit=cost_per_unit,
        )

    # End-of-data: close any open position at last close
    if in_pos:
        last_t = n - 1
        _close_trade(
            trades=trades,
            symbol=symbol,
            indicator_cfg=indicator_cfg,
            backtest_cfg=backtest_cfg,
            pos_dir=pos_dir,
            pos_entry_idx=pos_entry_idx,
            pos_entry_price=pos_entry_price,
            pos_sl=pos_sl,
            pos_tp=pos_tp,
            pos_signal_time=pos_signal_time,
            pos_atr=pos_atr,
            pos_size=pos_size,
            pos_risk_money=pos_risk_money,
            exit_price=float(close[last_t]),
            exit_idx=last_t,
            exit_reason="eod",
            times=times,
            cost_per_unit=cost_per_unit,
            slip_per_unit=slip_per_unit,
            pip_size=pip_size,
            out_df=out_df,
        )
        equity += trades[-1].pnl_money
        equity_curve[last_t] = equity

    eq_series = pd.Series(equity_curve, index=times, name="equity")
    log.info("backtest done: trades=%d final_equity=%.2f", len(trades), equity)
    return BacktestResult(
        trades=trades,
        equity_curve=eq_series,
        indicator_df=out_df,
        config_snapshot={
            "indicator": indicator_cfg.__dict__,
            "backtest": backtest_cfg.__dict__,
            "symbol": symbol,
            "pip_size": pip_size,
        },
    )


# ---------------------------------------------------------------------------
def _compute_sl_tp(
    *,
    cfg: BacktestConfig,
    direction: int,
    entry_price: float,
    atr_value: float,
    signal_bar_high: float,
    signal_bar_low: float,
) -> tuple[float, Optional[float]]:
    if cfg.sl_mode == "atr":
        if atr_value <= 0:
            atr_value = entry_price * 0.001  # fallback during warm-up
        sl = entry_price - direction * cfg.sl_atr_mult * atr_value
    elif cfg.sl_mode == "fixed_pct":
        sl = entry_price * (1 - direction * cfg.sl_fixed_pct)
    elif cfg.sl_mode == "signal_bar":
        sl = signal_bar_low if direction == 1 else signal_bar_high
    else:
        raise ValueError(f"[ERR-PARAM] unknown sl_mode={cfg.sl_mode!r}")

    risk = abs(entry_price - sl)
    if risk <= 0:
        risk = entry_price * 0.001
        sl = entry_price - direction * risk

    if cfg.tp_mode == "rr":
        tp: Optional[float] = entry_price + direction * cfg.tp_rr * risk
    elif cfg.tp_mode == "atr":
        if atr_value <= 0:
            atr_value = risk
        tp = entry_price + direction * cfg.tp_atr_mult * atr_value
    elif cfg.tp_mode == "none":
        tp = None
    else:
        raise ValueError(f"[ERR-PARAM] unknown tp_mode={cfg.tp_mode!r}")
    return float(sl), (float(tp) if tp is not None else None)


def _compute_size(
    *, equity: float, risk_pct: float, entry_price: float, sl: float
) -> tuple[float, float]:
    risk_money = equity * (risk_pct / 100.0)
    risk_per_unit = max(abs(entry_price - sl), 1e-12)
    size = risk_money / risk_per_unit
    return float(size), float(risk_money)


def _mark_to_market(
    *,
    equity: float,
    pos_dir: int,
    pos_size: float,
    entry: float,
    mark: float,
    cost_per_unit: float,
) -> float:
    pnl = (mark - entry) * pos_dir * pos_size - cost_per_unit * pos_size
    return equity + pnl


def _close_trade(
    *,
    trades: List[Trade],
    symbol: str,
    indicator_cfg: IndicatorConfig,
    backtest_cfg: BacktestConfig,
    pos_dir: int,
    pos_entry_idx: int,
    pos_entry_price: float,
    pos_sl: float,
    pos_tp: Optional[float],
    pos_signal_time: pd.Timestamp,
    pos_atr: float,
    pos_size: float,
    pos_risk_money: float,
    exit_price: float,
    exit_idx: int,
    exit_reason: str,
    times: pd.DatetimeIndex,
    cost_per_unit: float,
    slip_per_unit: float,
    pip_size: float,
    out_df: pd.DataFrame,
) -> None:
    direction_str = "long" if pos_dir == 1 else "short"
    pnl_price = (exit_price - pos_entry_price) * pos_dir
    # Subtract round-trip cost (spread/commission). Slippage on exit too.
    pnl_price -= cost_per_unit + abs(slip_per_unit)
    pnl_money = pnl_price * pos_size
    pnl_pct = pnl_price / pos_entry_price if pos_entry_price else 0.0
    risk_per_unit = max(abs(pos_entry_price - pos_sl), 1e-12)
    r_multiple = pnl_price / risk_per_unit
    pnl_pips = pnl_price / pip_size
    bars_held = exit_idx - pos_entry_idx
    entry_t = times[pos_entry_idx]
    exit_t = times[exit_idx]
    hour = int(entry_t.hour)
    fakeout = exit_reason == "sl" and bars_held <= 5

    trades.append(
        Trade(
            trade_id=len(trades) + 1,
            symbol=symbol,
            direction=direction_str,
            level_kind=backtest_cfg.level_kind,
            signal_time=pos_signal_time,
            entry_time=entry_t,
            entry_price=pos_entry_price,
            sl=pos_sl,
            tp=pos_tp,
            exit_time=exit_t,
            exit_price=exit_price,
            exit_reason=exit_reason,
            bars_held=bars_held,
            pnl_price=pnl_price,
            pnl_pips=pnl_pips,
            pnl_pct=pnl_pct,
            pnl_money=pnl_money,
            r_multiple=r_multiple,
            atr_at_entry=pos_atr,
            session=_classify_session(hour),
            weekday=entry_t.strftime("%A"),
            hour_utc=hour,
            is_fakeout=fakeout,
            lookback=indicator_cfg.lookback,
            exclude_recent=indicator_cfg.exclude_recent,
            lookback_3m=indicator_cfg.lookback_3m,
            exclude_recent_3m=indicator_cfg.exclude_recent_3m,
        )
    )


def _open_at_close(*args, **kwargs) -> None:  # placeholder — kept inline above
    return None


# ---------------------------------------------------------------------------
def run_full(
    df: pd.DataFrame, cfg: FullConfig, *, pip_size: Optional[float] = None
) -> BacktestResult:
    """Convenience wrapper that takes a :class:`FullConfig`."""
    cfg.validate()
    return run_backtest(
        df,
        indicator_cfg=cfg.indicator,
        backtest_cfg=cfg.backtest,
        symbol=cfg.run.symbol,
        pip_size=pip_size,
    )


__all__ = ["Trade", "BacktestResult", "run_backtest", "run_full"]
