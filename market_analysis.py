"""
Market Analysis – multi-timeframe structure, supply/demand zone detection,
and indicator computation for the MT5 Auto-Trading Bot.
"""

import logging

import numpy as np
import pandas as pd
import ta

import config

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════
# 1. SWING HIGHS / LOWS
# ═══════════════════════════════════════════════════════════════════
def detect_swing_highs(df: pd.DataFrame, left: int = 5, right: int = 5) -> pd.Series:
    """Return a boolean Series marking rows that are swing highs."""
    highs = df["high"].values
    swing = np.zeros(len(highs), dtype=bool)
    for i in range(left, len(highs) - right):
        if all(highs[i] >= highs[i - j] for j in range(1, left + 1)) and all(
            highs[i] >= highs[i + j] for j in range(1, right + 1)
        ):
            swing[i] = True
    return pd.Series(swing, index=df.index)


def detect_swing_lows(df: pd.DataFrame, left: int = 5, right: int = 5) -> pd.Series:
    """Return a boolean Series marking rows that are swing lows."""
    lows = df["low"].values
    swing = np.zeros(len(lows), dtype=bool)
    for i in range(left, len(lows) - right):
        if all(lows[i] <= lows[i - j] for j in range(1, left + 1)) and all(
            lows[i] <= lows[i + j] for j in range(1, right + 1)
        ):
            swing[i] = True
    return pd.Series(swing, index=df.index)


# ═══════════════════════════════════════════════════════════════════
# 2. MARKET STRUCTURE – Break of Structure (BOS) & Change of Character (CHoCH)
# ═══════════════════════════════════════════════════════════════════
def determine_market_structure(df: pd.DataFrame) -> str:
    """
    Analyse swing points to decide if the current structure is
    'bullish', 'bearish', or 'ranging'.
    """
    sh = detect_swing_highs(df)
    sl = detect_swing_lows(df)

    swing_high_prices = df.loc[sh, "high"].values
    swing_low_prices = df.loc[sl, "low"].values

    if len(swing_high_prices) < 2 or len(swing_low_prices) < 2:
        return "ranging"

    # Higher highs + higher lows → bullish
    hh = swing_high_prices[-1] > swing_high_prices[-2]
    hl = swing_low_prices[-1] > swing_low_prices[-2]
    # Lower lows + lower highs → bearish
    ll = swing_low_prices[-1] < swing_low_prices[-2]
    lh = swing_high_prices[-1] < swing_high_prices[-2]

    if hh and hl:
        return "bullish"
    if ll and lh:
        return "bearish"
    return "ranging"


def detect_bos_choch(df: pd.DataFrame) -> dict:
    """
    Detect the most recent Break of Structure / Change of Character.

    Returns
    -------
    dict with keys:
        type     : 'BOS' | 'CHoCH' | None
        direction: 'bullish' | 'bearish' | None
    """
    sh = detect_swing_highs(df)
    sl = detect_swing_lows(df)

    swing_highs = df.loc[sh, "high"].values
    swing_lows = df.loc[sl, "low"].values

    if len(swing_highs) < 2 or len(swing_lows) < 2:
        return {"type": None, "direction": None}

    last_close = df["close"].iloc[-1]

    # Bullish BOS: close breaks above the previous swing high
    if last_close > swing_highs[-2]:
        # If prior structure was bearish → CHoCH, else BOS
        prior = determine_market_structure(df.iloc[:-20]) if len(df) > 40 else "ranging"
        event = "CHoCH" if prior == "bearish" else "BOS"
        return {"type": event, "direction": "bullish"}

    # Bearish BOS: close breaks below the previous swing low
    if last_close < swing_lows[-2]:
        prior = determine_market_structure(df.iloc[:-20]) if len(df) > 40 else "ranging"
        event = "CHoCH" if prior == "bullish" else "BOS"
        return {"type": event, "direction": "bearish"}

    return {"type": None, "direction": None}


# ═══════════════════════════════════════════════════════════════════
# 3. SUPPLY / DEMAND ZONES
# ═══════════════════════════════════════════════════════════════════
def detect_supply_zones(df: pd.DataFrame, lookback: int | None = None) -> list[dict]:
    """
    Identify supply zones (potential sell zones).
    A supply zone forms at a strong bearish candle before a significant drop.

    Returns a list of dicts: {high, low, index, touches}
    """
    lookback = lookback or config.ZONE_LOOKBACK
    zones: list[dict] = []
    data = df.tail(lookback).reset_index(drop=True)

    for i in range(2, len(data) - 1):
        body = abs(data["close"].iloc[i] - data["open"].iloc[i])
        rng = data["high"].iloc[i] - data["low"].iloc[i]
        if rng == 0:
            continue

        is_bearish = data["close"].iloc[i] < data["open"].iloc[i]
        strong = body / rng >= config.ZONE_BODY_RATIO

        # The candle after should continue downward
        continued = data["close"].iloc[i + 1] < data["low"].iloc[i] if (i + 1) < len(data) else False

        if is_bearish and strong and continued:
            zone = {
                "high": float(data["high"].iloc[i]),
                "low": float(data["open"].iloc[i]),  # zone body top
                "index": i,
                "touches": 0,
            }
            zones.append(zone)

    # Count re-touches and filter
    zones = _count_zone_touches(data, zones, side="supply")
    return zones


def detect_demand_zones(df: pd.DataFrame, lookback: int | None = None) -> list[dict]:
    """
    Identify demand zones (potential buy zones).

    Returns a list of dicts: {high, low, index, touches}
    """
    lookback = lookback or config.ZONE_LOOKBACK
    zones: list[dict] = []
    data = df.tail(lookback).reset_index(drop=True)

    for i in range(2, len(data) - 1):
        body = abs(data["close"].iloc[i] - data["open"].iloc[i])
        rng = data["high"].iloc[i] - data["low"].iloc[i]
        if rng == 0:
            continue

        is_bullish = data["close"].iloc[i] > data["open"].iloc[i]
        strong = body / rng >= config.ZONE_BODY_RATIO

        continued = data["close"].iloc[i + 1] > data["high"].iloc[i] if (i + 1) < len(data) else False

        if is_bullish and strong and continued:
            zone = {
                "high": float(data["close"].iloc[i]),  # zone body top
                "low": float(data["low"].iloc[i]),
                "index": i,
                "touches": 0,
            }
            zones.append(zone)

    zones = _count_zone_touches(data, zones, side="demand")
    return zones


def _count_zone_touches(
    data: pd.DataFrame, zones: list[dict], side: str
) -> list[dict]:
    """Count how many candles re-enter each zone after formation and filter."""
    valid = []
    for z in zones:
        touches = 0
        start = z["index"] + 2
        for j in range(start, len(data)):
            if side == "supply" and data["high"].iloc[j] >= z["low"]:
                touches += 1
            elif side == "demand" and data["low"].iloc[j] <= z["high"]:
                touches += 1
        z["touches"] = touches
        if touches < config.ZONE_TOUCH_INVALIDATION:
            valid.append(z)
    return valid


# ═══════════════════════════════════════════════════════════════════
# 4. INDICATORS
# ═══════════════════════════════════════════════════════════════════
def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Add EMA and RSI columns in-place and return the DataFrame."""
    df = df.copy()
    df["ema_fast"] = ta.trend.ema_indicator(df["close"], window=config.EMA_FAST_PERIOD)
    df["ema_slow"] = ta.trend.ema_indicator(df["close"], window=config.EMA_SLOW_PERIOD)
    df["rsi"] = ta.momentum.rsi(df["close"], window=config.RSI_PERIOD)
    return df


# ═══════════════════════════════════════════════════════════════════
# 5. FAIR VALUE GAP (FVG)
# ═══════════════════════════════════════════════════════════════════
def detect_fvg(df: pd.DataFrame) -> list[dict]:
    """
    Detect Fair Value Gaps in the last section of the DataFrame.
    Returns list of {type: 'bullish'|'bearish', high, low, index}.
    """
    fvgs: list[dict] = []
    for i in range(2, len(df)):
        # Bullish FVG: candle[i] low > candle[i-2] high
        if df["low"].iloc[i] > df["high"].iloc[i - 2]:
            fvgs.append(
                {
                    "type": "bullish",
                    "high": float(df["low"].iloc[i]),
                    "low": float(df["high"].iloc[i - 2]),
                    "index": i,
                }
            )
        # Bearish FVG: candle[i] high < candle[i-2] low
        if df["high"].iloc[i] < df["low"].iloc[i - 2]:
            fvgs.append(
                {
                    "type": "bearish",
                    "high": float(df["low"].iloc[i - 2]),
                    "low": float(df["high"].iloc[i]),
                    "index": i,
                }
            )
    return fvgs


# ═══════════════════════════════════════════════════════════════════
# 6. ENGULFING CANDLE PATTERN
# ═══════════════════════════════════════════════════════════════════
def detect_engulfing(df: pd.DataFrame) -> str | None:
    """
    Check whether the last completed candle is an engulfing pattern.
    Returns 'bullish', 'bearish', or None.
    """
    if len(df) < 3:
        return None

    prev = df.iloc[-3]  # completed candle before last
    curr = df.iloc[-2]  # last completed candle

    # Bullish engulfing
    if (
        curr["close"] > curr["open"]
        and prev["close"] < prev["open"]
        and curr["close"] > prev["open"]
        and curr["open"] < prev["close"]
    ):
        return "bullish"

    # Bearish engulfing
    if (
        curr["close"] < curr["open"]
        and prev["close"] > prev["open"]
        and curr["close"] < prev["open"]
        and curr["open"] > prev["close"]
    ):
        return "bearish"

    return None
