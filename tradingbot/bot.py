"""Paper trading bot orchestrator."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import pandas as pd

from tradingbot.config import BotConfig
from tradingbot.data import fetch_history
from tradingbot.logger import get_logger
from tradingbot.risk_manager import RiskManager, PositionSizeResult
from tradingbot.strategies.base import BaseStrategy, Signal

logger = get_logger(__name__)


@dataclass
class OpenPosition:
    """Tracks a live/paper open position."""

    symbol: str
    entry_price: float
    shares: int
    stop_loss_price: float
    take_profit_price: float


@dataclass
class PaperPortfolio:
    """Simulated portfolio state."""

    cash: float
    positions: Dict[str, OpenPosition] = field(default_factory=dict)

    @property
    def open_position_count(self) -> int:
        return len(self.positions)

    def equity(self, prices: Dict[str, float]) -> float:
        """Mark-to-market portfolio value."""
        mtm = sum(
            pos.shares * prices.get(pos.symbol, pos.entry_price)
            for pos in self.positions.values()
        )
        return self.cash + mtm


def _build_strategy(cfg: BotConfig) -> BaseStrategy:
    """Instantiate the strategy selected in the configuration."""
    name = cfg.strategy
    if name == "moving_average":
        from tradingbot.strategies.moving_average import MovingAverageCrossover

        ma = cfg.strategies.moving_average
        return MovingAverageCrossover(
            short_window=ma.short_window,
            long_window=ma.long_window,
        )
    elif name == "rsi":
        from tradingbot.strategies.rsi import RSIStrategy

        r = cfg.strategies.rsi
        return RSIStrategy(period=r.period, oversold=r.oversold, overbought=r.overbought)
    else:
        raise ValueError(f"Unknown strategy '{name}'. Choose 'moving_average' or 'rsi'.")


class PaperTradingBot:
    """Simulated (paper) trading bot.

    Runs a single iteration: fetches the latest data for each configured
    symbol, evaluates the strategy, and executes simulated orders.

    Args:
        cfg: Bot configuration.
    """

    def __init__(self, cfg: BotConfig) -> None:
        self.cfg = cfg
        self.strategy = _build_strategy(cfg)
        self.risk_manager = RiskManager(
            max_position_pct=cfg.risk.max_position_pct,
            stop_loss_pct=cfg.risk.stop_loss_pct,
            take_profit_pct=cfg.risk.take_profit_pct,
            max_open_positions=cfg.risk.max_open_positions,
        )
        self.portfolio = PaperPortfolio(cash=cfg.portfolio.initial_capital)
        logger.info(
            "PaperTradingBot initialised | strategy=%s | capital=%.2f",
            self.strategy.name,
            cfg.portfolio.initial_capital,
        )

    def run_once(self) -> None:
        """Fetch data and evaluate signals for all configured symbols."""
        logger.info("--- Running signal evaluation ---")
        current_prices: Dict[str, float] = {}

        for symbol in self.cfg.symbols:
            try:
                data = fetch_history(
                    symbol,
                    lookback_days=self.cfg.data.lookback_days,
                    interval=self.cfg.data.interval,
                )
            except Exception as exc:
                logger.error("Failed to fetch data for %s: %s", symbol, exc)
                continue

            current_price = float(data["Close"].iloc[-1])
            current_prices[symbol] = current_price

            # --- Exit logic ---
            if symbol in self.portfolio.positions:
                pos = self.portfolio.positions[symbol]
                exit_reason: Optional[str] = None

                if self.risk_manager.should_stop_loss(pos.entry_price, current_price):
                    exit_reason = "stop_loss"
                elif self.risk_manager.should_take_profit(pos.entry_price, current_price):
                    exit_reason = "take_profit"
                else:
                    try:
                        result = self.strategy.generate_signal(data)
                        if result.signal == Signal.SELL:
                            exit_reason = "signal"
                    except ValueError as exc:
                        logger.warning("Strategy error for %s: %s", symbol, exc)

                if exit_reason:
                    self._close_position(symbol, current_price, exit_reason)

            # --- Entry logic ---
            if symbol not in self.portfolio.positions:
                try:
                    result = self.strategy.generate_signal(data)
                except ValueError as exc:
                    logger.warning("Strategy error for %s: %s", symbol, exc)
                    continue

                if result.signal == Signal.BUY:
                    equity = self.portfolio.equity(current_prices)
                    ps: Optional[PositionSizeResult] = self.risk_manager.calculate_position_size(
                        portfolio_value=equity,
                        entry_price=current_price,
                        open_positions=self.portfolio.open_position_count,
                    )
                    if ps is not None:
                        self._open_position(symbol, current_price, ps)

        equity = self.portfolio.equity(current_prices)
        logger.info(
            "Portfolio | cash=%.2f | positions=%d | equity=%.2f",
            self.portfolio.cash,
            self.portfolio.open_position_count,
            equity,
        )

    def _open_position(
        self, symbol: str, price: float, ps: PositionSizeResult
    ) -> None:
        self.portfolio.cash -= ps.position_value
        self.portfolio.positions[symbol] = OpenPosition(
            symbol=symbol,
            entry_price=price,
            shares=ps.shares,
            stop_loss_price=ps.stop_loss_price,
            take_profit_price=ps.take_profit_price,
        )
        logger.info(
            "BUY  %s @ %.4f | shares=%d | SL=%.4f | TP=%.4f",
            symbol, price, ps.shares, ps.stop_loss_price, ps.take_profit_price,
        )

    def _close_position(self, symbol: str, price: float, reason: str) -> None:
        pos = self.portfolio.positions.pop(symbol)
        proceeds = pos.shares * price
        pnl = proceeds - pos.shares * pos.entry_price
        self.portfolio.cash += proceeds
        logger.info(
            "SELL %s @ %.4f | reason=%s | shares=%d | PnL=%.2f",
            symbol, price, reason, pos.shares, pnl,
        )
