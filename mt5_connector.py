"""
MT5 Connector – handles initialisation, data retrieval and order operations
with the MetaTrader 5 terminal.
"""

import logging

import MetaTrader5 as mt5
import pandas as pd

import config

logger = logging.getLogger(__name__)


# ─── Timeframe mapping ────────────────────────────────────────────
_TF_MAP = {
    "M1": mt5.TIMEFRAME_M1,
    "M5": mt5.TIMEFRAME_M5,
    "M15": mt5.TIMEFRAME_M15,
    "M30": mt5.TIMEFRAME_M30,
    "H1": mt5.TIMEFRAME_H1,
    "H4": mt5.TIMEFRAME_H4,
    "D1": mt5.TIMEFRAME_D1,
    "W1": mt5.TIMEFRAME_W1,
    "MN1": mt5.TIMEFRAME_MN1,
}


def resolve_timeframe(tf_str: str) -> int:
    """Convert a human-readable timeframe string to an MT5 constant."""
    tf = _TF_MAP.get(tf_str.upper())
    if tf is None:
        raise ValueError(
            f"Unknown timeframe '{tf_str}'. Valid values: {list(_TF_MAP)}"
        )
    return tf


# ─── Connection ───────────────────────────────────────────────────
def connect() -> bool:
    """Initialise and log in to the MT5 terminal. Returns True on success."""
    init_kwargs: dict = {}
    if config.MT5_PATH:
        init_kwargs["path"] = config.MT5_PATH
    if config.MT5_LOGIN:
        init_kwargs["login"] = config.MT5_LOGIN
    if config.MT5_PASSWORD:
        init_kwargs["password"] = config.MT5_PASSWORD
    if config.MT5_SERVER:
        init_kwargs["server"] = config.MT5_SERVER

    if not mt5.initialize(**init_kwargs):
        logger.error("MT5 initialisation failed: %s", mt5.last_error())
        return False

    logger.info(
        "MT5 connected – account %s on %s",
        mt5.account_info().login,
        mt5.account_info().server,
    )
    return True


def disconnect():
    """Shut down the MT5 connection."""
    mt5.shutdown()
    logger.info("MT5 disconnected.")


# ─── Account info ─────────────────────────────────────────────────
def get_account_balance() -> float:
    """Return the current account balance."""
    info = mt5.account_info()
    if info is None:
        logger.error("Failed to get account info: %s", mt5.last_error())
        return 0.0
    return float(info.balance)


# ─── Market data ──────────────────────────────────────────────────
def get_candles(symbol: str, timeframe_str: str, count: int) -> pd.DataFrame:
    """
    Fetch *count* recent candles for *symbol* on *timeframe_str*.
    Returns a DataFrame with columns: time, open, high, low, close, tick_volume.
    """
    tf = resolve_timeframe(timeframe_str)
    rates = mt5.copy_rates_from_pos(symbol, tf, 0, count)
    if rates is None or len(rates) == 0:
        logger.warning(
            "No data returned for %s %s: %s", symbol, timeframe_str, mt5.last_error()
        )
        return pd.DataFrame()

    df = pd.DataFrame(rates)
    df["time"] = pd.to_datetime(df["time"], unit="s")
    return df[["time", "open", "high", "low", "close", "tick_volume"]]


def get_symbol_info(symbol: str):
    """Return the MT5 SymbolInfo object (or None)."""
    info = mt5.symbol_info(symbol)
    if info is None:
        logger.error("Symbol %s not found: %s", symbol, mt5.last_error())
    return info


def get_tick(symbol: str):
    """Return the latest tick for *symbol*."""
    tick = mt5.symbol_info_tick(symbol)
    if tick is None:
        logger.error("Tick unavailable for %s: %s", symbol, mt5.last_error())
    return tick


# ─── Order execution ─────────────────────────────────────────────
def send_order(
    symbol: str,
    order_type: str,
    volume: float,
    price: float,
    sl: float,
    tp: float,
    comment: str = "AutoBot",
    magic: int = 123456,
):
    """
    Send a market order.

    Parameters
    ----------
    order_type : "BUY" or "SELL"
    price      : entry price (ask for BUY, bid for SELL)
    """
    type_map = {"BUY": mt5.ORDER_TYPE_BUY, "SELL": mt5.ORDER_TYPE_SELL}
    mt5_type = type_map.get(order_type.upper())
    if mt5_type is None:
        logger.error("Invalid order type: %s", order_type)
        return None

    filling_map = {
        "IOC": mt5.ORDER_FILLING_IOC,
        "FOK": mt5.ORDER_FILLING_FOK,
        "RETURN": mt5.ORDER_FILLING_RETURN,
    }
    filling_type = filling_map.get(config.ORDER_FILLING_TYPE, mt5.ORDER_FILLING_IOC)

    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": round(volume, 2),
        "type": mt5_type,
        "price": price,
        "sl": round(sl, _price_digits(symbol)),
        "tp": round(tp, _price_digits(symbol)),
        "deviation": 20,
        "magic": magic,
        "comment": comment,
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": filling_type,
    }

    result = mt5.order_send(request)
    if result is None:
        logger.error("order_send returned None: %s", mt5.last_error())
        return None
    if result.retcode != mt5.TRADE_RETCODE_DONE:
        logger.error("Order failed – retcode %s: %s", result.retcode, result.comment)
        return None

    logger.info(
        "Order placed: %s %s %.2f lots @ %.5f  SL=%.5f  TP=%.5f  ticket=%s",
        order_type,
        symbol,
        volume,
        price,
        sl,
        tp,
        result.order,
    )
    return result


def modify_position(ticket: int, sl: float | None = None, tp: float | None = None):
    """Modify the SL and/or TP of an open position by ticket."""
    position = _get_position_by_ticket(ticket)
    if position is None:
        return None

    new_sl = sl if sl is not None else position.sl
    new_tp = tp if tp is not None else position.tp
    digits = _price_digits(position.symbol)

    request = {
        "action": mt5.TRADE_ACTION_SLTP,
        "position": ticket,
        "symbol": position.symbol,
        "sl": round(new_sl, digits),
        "tp": round(new_tp, digits),
    }

    result = mt5.order_send(request)
    if result is None:
        logger.error("modify_position returned None: %s", mt5.last_error())
        return None
    if result.retcode != mt5.TRADE_RETCODE_DONE:
        logger.error(
            "Modify failed – retcode %s: %s", result.retcode, result.comment
        )
        return None

    logger.info("Position %s modified – SL=%.5f  TP=%.5f", ticket, new_sl, new_tp)
    return result


def get_open_positions(symbol: str, magic: int = 123456) -> list:
    """Return a list of open positions for *symbol* with the given magic number."""
    positions = mt5.positions_get(symbol=symbol)
    if positions is None:
        return []
    return [p for p in positions if p.magic == magic]


# ─── Helpers ──────────────────────────────────────────────────────
def _price_digits(symbol: str) -> int:
    info = get_symbol_info(symbol)
    return info.digits if info else 5


def _get_position_by_ticket(ticket: int):
    positions = mt5.positions_get(ticket=ticket)
    if positions is None or len(positions) == 0:
        logger.error("Position %s not found.", ticket)
        return None
    return positions[0]
