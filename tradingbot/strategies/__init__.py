"""Strategies package."""

from tradingbot.strategies.base import BaseStrategy, Signal, StrategyResult
from tradingbot.strategies.moving_average import MovingAverageCrossover
from tradingbot.strategies.rsi import RSIStrategy

__all__ = [
    "BaseStrategy",
    "Signal",
    "StrategyResult",
    "MovingAverageCrossover",
    "RSIStrategy",
]
