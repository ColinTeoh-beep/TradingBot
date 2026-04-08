"""
Trade Manager – handles order execution with layering, break-even,
and trailing-stop logic for the MT5 Auto-Trading Bot.
"""

import logging

import config
import mt5_connector as mt5c
import risk_management as rm

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════
# 1. EXECUTE TRADE (with optional layering)
# ═══════════════════════════════════════════════════════════════════
def execute_trade(symbol: str, plan: dict) -> list[int]:
    """
    Place one or more market orders according to the trading plan.

    If layering is enabled, additional entries are placed at fixed
    intervals from the first entry.  **All layers share the SL and TP
    of the first entry.**

    Returns a list of order tickets (empty on total failure).
    """
    if not rm.can_open_trade(symbol):
        return []

    direction = plan["direction"]
    sl = plan["sl"]
    tp = plan["tp"]
    sl_points = plan["sl_points"]

    num_layers = config.MAX_LAYERS if config.LAYERING_ENABLED else 1
    lot_size = rm.calculate_lot_size(symbol, sl_points, num_layers)
    if lot_size <= 0:
        logger.error("Lot size is zero – trade aborted.")
        return []

    tickets: list[int] = []

    for layer_idx in range(num_layers):
        # Use live price for market execution
        tick = mt5c.get_tick(symbol)
        if tick is None:
            break
        exec_price = tick.ask if direction == "BUY" else tick.bid

        comment = f"AutoBot L{layer_idx + 1}/{num_layers}"
        result = mt5c.send_order(
            symbol=symbol,
            order_type=direction,
            volume=lot_size,
            price=exec_price,
            sl=sl,
            tp=tp,
            comment=comment,
        )
        if result is not None:
            tickets.append(result.order)
            logger.info(
                "Layer %d/%d placed – ticket %s @ %.5f",
                layer_idx + 1,
                num_layers,
                result.order,
                exec_price,
            )
        else:
            logger.warning("Layer %d/%d failed to execute.", layer_idx + 1, num_layers)

    return tickets


# ═══════════════════════════════════════════════════════════════════
# 2. BREAK-EVEN MANAGEMENT
# ═══════════════════════════════════════════════════════════════════
def manage_breakeven(symbol: str):
    """
    For each open position, if price has moved favourably by
    ``BREAKEVEN_TRIGGER_RR × SL distance``, move SL to entry +/- offset.
    """
    if not config.BREAKEVEN_ENABLED:
        return

    positions = mt5c.get_open_positions(symbol)
    tick = mt5c.get_tick(symbol)
    if tick is None:
        return

    info = mt5c.get_symbol_info(symbol)
    if info is None:
        return
    point = info.point

    for pos in positions:
        entry = pos.price_open
        current_sl = pos.sl
        sl_dist = abs(entry - current_sl)

        if sl_dist == 0:
            continue

        trigger_dist = sl_dist * config.BREAKEVEN_TRIGGER_RR
        offset = config.BREAKEVEN_OFFSET_POINTS * point

        if pos.type == 0:  # BUY
            current_price = tick.bid
            be_sl = entry + offset
            # Only move if not already at break-even or better
            if current_price >= entry + trigger_dist and current_sl < be_sl:
                mt5c.modify_position(pos.ticket, sl=be_sl)
                logger.info(
                    "Break-even: ticket %s SL moved to %.5f", pos.ticket, be_sl
                )

        elif pos.type == 1:  # SELL
            current_price = tick.ask
            be_sl = entry - offset
            if current_price <= entry - trigger_dist and current_sl > be_sl:
                mt5c.modify_position(pos.ticket, sl=be_sl)
                logger.info(
                    "Break-even: ticket %s SL moved to %.5f", pos.ticket, be_sl
                )


# ═══════════════════════════════════════════════════════════════════
# 3. TRAILING STOP
# ═══════════════════════════════════════════════════════════════════
def manage_trailing_stop(symbol: str):
    """
    Trail the SL behind the current price once profit exceeds
    ``TRAILING_ACTIVATION_RR × SL distance``.
    """
    if not config.TRAILING_STOP_ENABLED:
        return

    positions = mt5c.get_open_positions(symbol)
    tick = mt5c.get_tick(symbol)
    if tick is None:
        return

    info = mt5c.get_symbol_info(symbol)
    if info is None:
        return
    point = info.point
    trail_dist = config.TRAILING_DISTANCE_POINTS * point

    for pos in positions:
        entry = pos.price_open
        current_sl = pos.sl
        sl_dist = abs(entry - current_sl)

        if sl_dist == 0:
            continue

        activation_dist = sl_dist * config.TRAILING_ACTIVATION_RR

        if pos.type == 0:  # BUY
            current_price = tick.bid
            if current_price >= entry + activation_dist:
                new_sl = current_price - trail_dist
                if new_sl > current_sl:
                    mt5c.modify_position(pos.ticket, sl=new_sl)
                    logger.info(
                        "Trailing stop: ticket %s SL trailed to %.5f",
                        pos.ticket,
                        new_sl,
                    )

        elif pos.type == 1:  # SELL
            current_price = tick.ask
            if current_price <= entry - activation_dist:
                new_sl = current_price + trail_dist
                if new_sl < current_sl:
                    mt5c.modify_position(pos.ticket, sl=new_sl)
                    logger.info(
                        "Trailing stop: ticket %s SL trailed to %.5f",
                        pos.ticket,
                        new_sl,
                    )
