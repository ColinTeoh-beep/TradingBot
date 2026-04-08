"""Configuration loader for TradingBot."""

import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import yaml


@dataclass
class MAConfig:
    short_window: int = 20
    long_window: int = 50


@dataclass
class RSIConfig:
    period: int = 14
    oversold: float = 30.0
    overbought: float = 70.0


@dataclass
class StrategiesConfig:
    moving_average: MAConfig = field(default_factory=MAConfig)
    rsi: RSIConfig = field(default_factory=RSIConfig)


@dataclass
class RiskConfig:
    max_position_pct: float = 0.10
    stop_loss_pct: float = 0.05
    take_profit_pct: float = 0.15
    max_open_positions: int = 5


@dataclass
class PortfolioConfig:
    initial_capital: float = 100_000.0


@dataclass
class DataConfig:
    interval: str = "1d"
    lookback_days: int = 365


@dataclass
class LoggingConfig:
    level: str = "INFO"
    file: Optional[str] = None


@dataclass
class BotConfig:
    mode: str = "paper"
    symbols: List[str] = field(default_factory=lambda: ["SPY"])
    strategy: str = "moving_average"
    strategies: StrategiesConfig = field(default_factory=StrategiesConfig)
    risk: RiskConfig = field(default_factory=RiskConfig)
    portfolio: PortfolioConfig = field(default_factory=PortfolioConfig)
    data: DataConfig = field(default_factory=DataConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)


def load_config(path: str = "config.yaml") -> BotConfig:
    """Load configuration from a YAML file.

    Args:
        path: Path to the YAML configuration file.

    Returns:
        Populated BotConfig instance.

    Raises:
        FileNotFoundError: If the config file does not exist.
        ValueError: If required fields contain invalid values.
    """
    if not os.path.exists(path):
        raise FileNotFoundError(f"Config file not found: {path}")

    with open(path, "r") as fh:
        raw = yaml.safe_load(fh) or {}

    cfg = BotConfig()

    cfg.mode = raw.get("mode", cfg.mode)
    if cfg.mode not in ("paper", "live"):
        raise ValueError(f"Invalid mode '{cfg.mode}'. Must be 'paper' or 'live'.")

    cfg.symbols = raw.get("symbols", cfg.symbols)
    cfg.strategy = raw.get("strategy", cfg.strategy)

    strat_raw = raw.get("strategies", {})
    ma_raw = strat_raw.get("moving_average", {})
    cfg.strategies.moving_average = MAConfig(
        short_window=ma_raw.get("short_window", 20),
        long_window=ma_raw.get("long_window", 50),
    )
    rsi_raw = strat_raw.get("rsi", {})
    cfg.strategies.rsi = RSIConfig(
        period=rsi_raw.get("period", 14),
        oversold=rsi_raw.get("oversold", 30.0),
        overbought=rsi_raw.get("overbought", 70.0),
    )

    risk_raw = raw.get("risk", {})
    cfg.risk = RiskConfig(
        max_position_pct=risk_raw.get("max_position_pct", 0.10),
        stop_loss_pct=risk_raw.get("stop_loss_pct", 0.05),
        take_profit_pct=risk_raw.get("take_profit_pct", 0.15),
        max_open_positions=risk_raw.get("max_open_positions", 5),
    )

    portfolio_raw = raw.get("portfolio", {})
    cfg.portfolio = PortfolioConfig(
        initial_capital=portfolio_raw.get("initial_capital", 100_000.0),
    )

    data_raw = raw.get("data", {})
    cfg.data = DataConfig(
        interval=data_raw.get("interval", "1d"),
        lookback_days=data_raw.get("lookback_days", 365),
    )

    log_raw = raw.get("logging", {})
    cfg.logging = LoggingConfig(
        level=log_raw.get("level", "INFO"),
        file=log_raw.get("file"),
    )

    return cfg
