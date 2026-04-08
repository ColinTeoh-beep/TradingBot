# MT5 Auto-Trading Bot

A fully automated trading bot for **MetaTrader 5** written in Python. It performs multi-timeframe market analysis, identifies supply/demand zones, validates entries through lower-timeframe confluence checks, and manages open positions with break-even, trailing stop, and layering features.

---

## Features

| Feature | Description |
|---|---|
| **Multi-TF Analysis** | Higher timeframe for market structure & zones; lower timeframe for entry signals. |
| **Supply / Demand Zones** | Automatic detection of institutional-style zones with re-touch invalidation. |
| **Market Structure** | Swing-based BOS (Break of Structure) and CHoCH (Change of Character) detection. |
| **Confluence Engine** | Requires ≥ 3 confluences on the lower timeframe before opening a trade. |
| **Trading Plan** | Auto-calculated entry, SL, and TP based on zone boundaries and configurable RR ratio. |
| **Risk Management** | Per-trade risk sizing (% of balance), max open trades limit. |
| **Break-Even** | Moves SL to entry once price moves a configurable RR multiple in profit. |
| **Trailing Stop** | Trails SL behind price after a configurable activation threshold. |
| **Layering** | Opens multiple entries at staggered prices; all layers share the first entry's SL and TP. |

---

## Confluences Checked (Lower Timeframe)

1. **Market Structure** – BOS / CHoCH aligned with bias.
2. **EMA Alignment** – Fast EMA > Slow EMA for buys (and vice-versa), price above/below fast EMA.
3. **RSI** – Oversold for buys, overbought for sells.
4. **Engulfing Pattern** – Bullish or bearish engulfing candle.
5. **Fair Value Gap (FVG)** – Recent imbalance gap aligned with bias.

A trade is only taken when **at least 3** of these conditions are met (configurable via `MIN_CONFLUENCES`).

---

## Project Structure

```
TradingBot/
├── bot.py               # Main entry point & orchestrator loop
├── config.py            # All configurable parameters
├── mt5_connector.py     # MT5 connection, data fetching, order execution
├── market_analysis.py   # Swing detection, zones, structure, FVG, engulfing, indicators
├── confluence.py        # Lower-TF confluence engine
├── trading_plan.py      # Entry / SL / TP calculation
├── risk_management.py   # Lot sizing & trade limits
├── trade_manager.py     # Order execution, break-even, trailing stop, layering
├── requirements.txt     # Python dependencies
└── README.md
```

---

## Setup

### Prerequisites

- **Windows** with MetaTrader 5 terminal installed and logged in.
- **Python 3.10+**

### Installation

```bash
git clone https://github.com/ColinTeoh-beep/TradingBot.git
cd TradingBot
pip install -r requirements.txt
```

### Configuration

Edit `config.py` with your account details:

```python
MT5_LOGIN    = 12345678        # Your MT5 account number
MT5_PASSWORD = "your_password" # Your MT5 password
MT5_SERVER   = "YourBroker-Server"
MT5_PATH     = r"C:\Program Files\MetaTrader 5\terminal64.exe"  # Optional

SYMBOL             = "EURUSD"
HIGHER_TIMEFRAME   = "H4"
LOWER_TIMEFRAME    = "M15"

RISK_PERCENT       = 1.0   # Risk 1 % of balance per trade
RR_RATIO           = 2.0   # 1:2 risk-reward
```

See `config.py` for the full list of parameters including break-even thresholds, trailing-stop distances, layering settings, and confluence toggles.

### Running

```bash
python bot.py
```

The bot will:
1. Connect to MT5.
2. Continuously analyse the market on each loop interval.
3. Open trades when conditions are met.
4. Manage open positions (break-even, trailing stop).
5. Log all activity to the console and `trading_bot.log`.

Press `Ctrl+C` to stop.

---

## How It Works

```
┌─────────────────────────────────────┐
│          Higher Timeframe           │
│  • Determine market structure       │
│  • Detect supply / demand zones     │
│  • Decide bullish / bearish bias    │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│          Lower Timeframe            │
│  • Check ≥ 3 confluences           │
│    (Structure, EMA, RSI,           │
│     Engulfing, FVG)                │
└──────────────┬──────────────────────┘
               │ Signal = True
               ▼
┌─────────────────────────────────────┐
│          Trading Plan               │
│  • Entry at zone boundary           │
│  • SL beyond zone + buffer          │
│  • TP = SL distance × RR ratio     │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│        Risk Management              │
│  • Lot size from % risk / SL dist  │
│  • Check max open trades            │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│        Trade Execution              │
│  • Place order(s)                   │
│  • Layering: stagger entries,       │
│    all share first SL & TP          │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│      Position Management            │
│  • Break-even after X RR            │
│  • Trailing stop after Y RR         │
└─────────────────────────────────────┘
```

---

## Risk Disclaimer

This software is provided for **educational purposes only**. Trading forex and CFDs carries significant risk. Past performance does not guarantee future results. Always test on a demo account before using real money. The authors accept no responsibility for financial losses.