"""Market data fetching utilities."""

from __future__ import annotations

import datetime
from typing import Dict, List, Optional

import pandas as pd
import yfinance as yf

from tradingbot.logger import get_logger

logger = get_logger(__name__)


def fetch_history(
    symbol: str,
    lookback_days: int = 365,
    interval: str = "1d",
    end: Optional[datetime.date] = None,
) -> pd.DataFrame:
    """Download OHLCV data for a single symbol.

    Args:
        symbol: Ticker symbol (e.g. "AAPL").
        lookback_days: Number of calendar days of history to fetch.
        interval: Bar interval (e.g. "1d", "1h", "15m").
        end: End date; defaults to today.

    Returns:
        DataFrame with columns Open, High, Low, Close, Volume indexed by datetime.

    Raises:
        ValueError: If no data is returned for the symbol.
    """
    end_date = end or datetime.date.today()
    start_date = end_date - datetime.timedelta(days=lookback_days)

    logger.debug("Fetching %s | %s → %s | interval=%s", symbol, start_date, end_date, interval)

    ticker = yf.Ticker(symbol)
    df = ticker.history(start=str(start_date), end=str(end_date), interval=interval, auto_adjust=True)

    if df.empty:
        raise ValueError(f"No data returned for symbol '{symbol}'.")

    df.index = pd.to_datetime(df.index)
    df = df[["Open", "High", "Low", "Close", "Volume"]].copy()
    df.sort_index(inplace=True)

    logger.debug("Fetched %d bars for %s", len(df), symbol)
    return df


def fetch_multiple(
    symbols: List[str],
    lookback_days: int = 365,
    interval: str = "1d",
    end: Optional[datetime.date] = None,
) -> Dict[str, pd.DataFrame]:
    """Download OHLCV data for multiple symbols.

    Args:
        symbols: List of ticker symbols.
        lookback_days: Number of calendar days of history.
        interval: Bar interval.
        end: End date; defaults to today.

    Returns:
        Mapping of symbol → DataFrame.
    """
    results: Dict[str, pd.DataFrame] = {}
    for symbol in symbols:
        try:
            results[symbol] = fetch_history(symbol, lookback_days, interval, end)
        except Exception as exc:
            logger.warning("Could not fetch data for %s: %s", symbol, exc)
    return results
