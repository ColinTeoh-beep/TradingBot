#!/usr/bin/env python3
"""TradingBot entry point.

Usage
-----
  # Paper trade (one shot evaluation):
  python main.py --mode paper

  # Backtest a strategy over historical data:
  python main.py --mode backtest --symbol AAPL

  # Use a custom config file:
  python main.py --config my_config.yaml --mode backtest --symbol MSFT
"""

import argparse
import sys

from tradingbot.config import load_config
from tradingbot.logger import get_logger


def _run_backtest(args: argparse.Namespace) -> None:
    from tradingbot.backtester import Backtester
    from tradingbot.bot import _build_strategy
    from tradingbot.data import fetch_history
    from tradingbot.risk_manager import RiskManager

    cfg = load_config(args.config)
    logger = get_logger("main", cfg.logging.level, cfg.logging.file)

    strategy = _build_strategy(cfg)
    risk_manager = RiskManager(
        max_position_pct=cfg.risk.max_position_pct,
        stop_loss_pct=cfg.risk.stop_loss_pct,
        take_profit_pct=cfg.risk.take_profit_pct,
        max_open_positions=cfg.risk.max_open_positions,
    )
    backtester = Backtester(
        strategy=strategy,
        risk_manager=risk_manager,
        initial_capital=cfg.portfolio.initial_capital,
    )

    symbol = args.symbol or cfg.symbols[0]
    logger.info("Fetching historical data for %s …", symbol)
    data = fetch_history(symbol, lookback_days=cfg.data.lookback_days, interval=cfg.data.interval)

    logger.info("Running backtest for %s with strategy %s …", symbol, strategy.name)
    result = backtester.run(symbol, data)

    print()
    print(result.summary())
    print()

    if args.verbose and result.trades:
        print("--- Trade Log ---")
        for t in result.trades:
            print(
                f"  {t.entry_date.date()} → {t.exit_date.date()} | "
                f"{t.symbol} | entry={t.entry_price:.4f} exit={t.exit_price:.4f} | "
                f"shares={t.shares} | pnl={t.pnl:+.2f} ({t.pnl_pct:+.2f}%) | {t.exit_reason}"
            )


def _run_paper(args: argparse.Namespace) -> None:
    from tradingbot.bot import PaperTradingBot

    cfg = load_config(args.config)
    logger = get_logger("main", cfg.logging.level, cfg.logging.file)

    bot = PaperTradingBot(cfg)
    logger.info("Starting paper trading session …")
    bot.run_once()
    logger.info("Paper trading session complete.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="TradingBot – profitable algorithmic trading bot",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--mode",
        choices=["paper", "backtest"],
        default="paper",
        help="Operating mode (default: paper)",
    )
    parser.add_argument(
        "--config",
        default="config.yaml",
        help="Path to YAML configuration file (default: config.yaml)",
    )
    parser.add_argument(
        "--symbol",
        default=None,
        help="Symbol to use for backtest mode (overrides config)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print full trade log in backtest mode",
    )

    args = parser.parse_args()

    if args.mode == "backtest":
        _run_backtest(args)
    else:
        _run_paper(args)


if __name__ == "__main__":
    main()
