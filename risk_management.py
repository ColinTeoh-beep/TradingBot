"""
Risk Management – lot-size calculation based on account balance and risk %.
"""

import logging
import math

import config
import mt5_connector as mt5c

logger = logging.getLogger(__name__)


def calculate_lot_size(
    symbol: str,
    sl_points: float,
    num_layers: int = 1,
) -> float:
    """
    Compute lot size so that the *total* risk across all layers equals
    ``config.RISK_PERCENT`` of the account balance.

    Parameters
    ----------
    sl_points  : distance from entry to SL in *points*
    num_layers : number of layered entries sharing the risk

    Returns the per-layer lot size (rounded down to 0.01).
    """
    balance = mt5c.get_account_balance()
    if balance <= 0:
        logger.error("Balance is zero or negative – cannot size position.")
        return 0.0

    info = mt5c.get_symbol_info(symbol)
    if info is None:
        return 0.0

    risk_amount = balance * (config.RISK_PERCENT / 100.0)

    # pip_value = contract_size * point
    pip_value = info.trade_contract_size * info.point
    if pip_value == 0:
        logger.error("Pip value is zero – check symbol info.")
        return 0.0

    total_lots = risk_amount / (sl_points * pip_value)
    per_layer = total_lots / max(num_layers, 1)

    # Clamp to broker limits and round down to 0.01
    # Round down to 0.01, then clamp between broker min/max
    per_layer = math.floor(per_layer * 100) / 100
    per_layer = max(info.volume_min, min(per_layer, info.volume_max))

    logger.info(
        "Risk calc: balance=%.2f  risk%%=%.1f  risk$=%.2f  "
        "SL_pts=%.0f  total_lots=%.4f  layers=%d  per_layer=%.2f",
        balance,
        config.RISK_PERCENT,
        risk_amount,
        sl_points,
        total_lots,
        num_layers,
        per_layer,
    )
    return per_layer


def can_open_trade(symbol: str) -> bool:
    """Return True if we are below the maximum open-trade limit."""
    open_positions = mt5c.get_open_positions(symbol)
    count = len(open_positions)
    allowed = count < config.MAX_OPEN_TRADES
    if not allowed:
        logger.info(
            "Max open trades reached (%d/%d) for %s.",
            count,
            config.MAX_OPEN_TRADES,
            symbol,
        )
    return allowed
