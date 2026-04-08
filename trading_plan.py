"""
Trading Plan – builds a concrete plan (entry, SL, TP) based on the
detected zone and bias.
"""

import logging

import config
import mt5_connector as mt5c

logger = logging.getLogger(__name__)


def build_plan(
    symbol: str,
    bias: str,
    zone: dict,
) -> dict | None:
    """
    Create a trading plan.

    Parameters
    ----------
    symbol : MT5 symbol name
    bias   : 'bullish' (buy) or 'bearish' (sell)
    zone   : dict with 'high' and 'low' keys (supply or demand zone)

    Returns
    -------
    dict with keys: direction, entry, sl, tp, sl_points
    or None if the plan is invalid.
    """
    info = mt5c.get_symbol_info(symbol)
    if info is None:
        return None

    point = info.point
    tick = mt5c.get_tick(symbol)
    if tick is None:
        return None

    if bias == "bullish":
        # Buy at the top of the demand zone (or current ask if inside)
        entry = max(zone["high"], tick.ask)
        sl = zone["low"] - config.SL_BUFFER_POINTS * point
        sl_dist = entry - sl
        tp = entry + sl_dist * config.RR_RATIO
        direction = "BUY"

    elif bias == "bearish":
        # Sell at the bottom of the supply zone (or current bid if inside)
        entry = min(zone["low"], tick.bid)
        sl = zone["high"] + config.SL_BUFFER_POINTS * point
        sl_dist = sl - entry
        tp = entry - sl_dist * config.RR_RATIO
        direction = "SELL"
    else:
        logger.warning("Unknown bias: %s", bias)
        return None

    sl_points = sl_dist / point

    if sl_dist <= 0:
        logger.warning("SL distance is non-positive (%.5f). Plan rejected.", sl_dist)
        return None

    plan = {
        "direction": direction,
        "entry": round(entry, info.digits),
        "sl": round(sl, info.digits),
        "tp": round(tp, info.digits),
        "sl_points": sl_points,
    }

    logger.info(
        "Trading plan: %s %s  entry=%.5f  SL=%.5f  TP=%.5f  (SL %.0f pts, RR 1:%.1f)",
        direction,
        symbol,
        plan["entry"],
        plan["sl"],
        plan["tp"],
        sl_points,
        config.RR_RATIO,
    )
    return plan
