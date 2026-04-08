"""Strategy base class."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Optional

import pandas as pd


class Signal(Enum):
    """Trading signal emitted by a strategy."""

    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


@dataclass
class StrategyResult:
    """Encapsulates a strategy evaluation result.

    Attributes:
        signal: The action signal.
        price: The reference price at signal generation.
        indicator_values: Optional dict of indicator values for logging/debug.
    """

    signal: Signal
    price: float
    indicator_values: Optional[dict] = None


class BaseStrategy(ABC):
    """Abstract base class that all trading strategies must inherit from."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable strategy name."""

    @abstractmethod
    def generate_signal(self, data: pd.DataFrame) -> StrategyResult:
        """Evaluate the latest bar and return a trading signal.

        Args:
            data: OHLCV DataFrame sorted by time (most recent last).
                  Must contain at least a 'Close' column.

        Returns:
            StrategyResult with signal, reference price, and indicators.
        """
