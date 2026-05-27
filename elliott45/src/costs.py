"""Per-symbol realistic frictions for stress testing.

The ``cost_per_trade`` numbers are conservative round-trip spreads
expressed in the same price units as the OHLC data:

  * JPY pairs ........... 1 pip = 0.01 JPY, typical RT spread ~ 0.02 JPY
  * XAUUSD .............. 0.30-0.50 USD typical RT spread
  * XAGUSD .............. 0.03 USD typical RT spread
  * NAS100/SPX500 ....... 1-2 index points

The "strict" preset roughly doubles each so we credit slippage on
top of spread; combined with ``slippage_atr_mult`` it yields a worst-case
friction far above any reputable retail broker.
"""

from __future__ import annotations

REALISTIC_COSTS: dict[str, float] = {
    "USDJPY": 0.02,
    "EURJPY": 0.02,
    "AUDJPY": 0.02,
    "CHFJPY": 0.03,
    "GBPJPY": 0.03,
    "XAUUSD": 0.50,
    "XAGUSD": 0.03,
    "NAS100": 2.0,
    "SPX500": 1.0,
}

STRICT_COSTS: dict[str, float] = {
    "USDJPY": 0.04,
    "EURJPY": 0.04,
    "AUDJPY": 0.04,
    "CHFJPY": 0.05,
    "GBPJPY": 0.05,
    "XAUUSD": 1.00,
    "XAGUSD": 0.06,
    "NAS100": 4.0,
    "SPX500": 2.0,
}


def cost_for(symbol: str, mode: str = "realistic") -> float:
    table = STRICT_COSTS if mode == "strict" else REALISTIC_COSTS
    return table.get(symbol, 0.0)
