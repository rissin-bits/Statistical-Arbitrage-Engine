# Statistical Arbitrage Engine

A quantitative trading system that detects and exploits cross-exchange price dislocations using a 5-filter signal pipeline, automated backtesting, and adaptive parameter optimization.

## Overview

The engine monitors the same asset across multiple exchanges. When prices temporarily diverge, it identifies genuine arbitrage opportunities by filtering out noise through five progressively strict filters, then executes trades and tracks P&L.

## Architecture

```
RAW PRICE DATA (N ticks × 3 exchanges)
       │
       ▼
┌─────────────────────────────────────┐
│  Filter 1: Spread Threshold         │  Is there a price gap?
│  Filter 2: Cost Adjustment          │  Profitable after fees?
│  Filter 3: Persistence              │  Real or one-tick glitch?
│  Filter 4: Z-Score                  │  Statistically unusual?
│  Filter 5: Volatility-Adjusted      │  Large relative to vol?
└──────────────────┬──────────────────┘
                   ▼
            TRADEABLE SIGNALS
                   │
                   ▼
┌─────────────────────────────────────┐
│  Backtest Engine                     │
│  • Entry at signal + 1 tick latency  │
│  • Exit: z-revert | stop-loss | max  │
│  • P&L after real fees & slippage    │
└──────────────────┬──────────────────┘
                   ▼
         PERFORMANCE METRICS
```

## The 5-Filter Pipeline

### Filter 1 — Spread Threshold
Computes the max spread across all exchange pairs in basis points. Discards ticks where the spread is too small to be interesting.

### Filter 2 — Cost Adjustment
Subtracts exchange fees and slippage from the gross spread. Only passes if the net spread is positive — the trade must be profitable after all costs.

### Filter 3 — Persistence
Requires the spread to persist for N consecutive ticks. One-tick spikes are likely stale quotes or data glitches, not real opportunities.

### Filter 4 — Z-Score
Normalizes the spread against its rolling history. A 7 bps spread is meaningless if the pair normally fluctuates 5–10 bps. Only passes if the spread is statistically unusual (|z| > threshold).

### Filter 5 — Volatility-Adjusted
Divides the spread by current realized volatility. A 10 bps spread during calm markets is meaningful; the same 10 bps during volatile markets is just noise. Only passes if spread/vol exceeds the threshold.

## Backtest Engine

- **Entry**: Signal tick + 1 (latency simulation)
- **Consecutive grouping**: Multiple signals on the same pair → one trade
- **Exit conditions**:
  - Z-score reversion (spread normalized → take profit)
  - Stop-loss (spread widened 15+ bps → cut loss)
  - Max hold (20 ticks → forced exit)
- **P&L**: Quantity × price change on both legs − round-trip fees

## Performance Metrics

The engine computes: Sharpe ratio, Sortino ratio, Calmar ratio, profit factor, win rate, max drawdown, Kelly criterion, P&L skewness/kurtosis, fee drag, and time-in-market efficiency.

## Data Generation

Synthetic data uses Geometric Brownian Motion:

- **True price**: GBM with configurable drift and volatility
- **Exchange prices**: True price + bias + microstructure noise + dislocations
- **Dislocations**: Random magnitude with exponential decay (mean-reverting)

Set `SEED = None` for random data each run, or a fixed integer for reproducibility.

## Real Data Testing

Tested on real BTC data from Binance, Coinbase, and Bybit (29,565 aligned 1-minute ticks). Result: zero trades — average spread of 1.82 bps vs minimum cost of 24 bps. The market is too efficient for this strategy at 1-minute granularity on major exchanges.

Also tested on SAND across Binance, MEXC, and Bybit (30,000 ticks). Spreads existed (avg 12.6 bps) but didn't mean-revert as expected — structural spreads, not temporary dislocations.

These honest negative results validate the engine's methodology — it refuses to trade when there's no genuine edge.

## Live Trading Dashboard

A React-based real-time trading dashboard (`trading_dashboard_v4.jsx`) that:
1. Generates 100K fresh random ticks on every run
2. Optimizes parameters on first 50K ticks (grid search)
3. Trades the next 50K with optimized parameters
4. Adaptively re-optimizes every 500 ticks based on recent performance
5. Displays live: prices, spreads, filter status, order book, P&L, metrics, parameter changes

### Running the Dashboard

```bash
npx create-react-app arb-engine
cd arb-engine
# Replace src/App.js with trading_dashboard_v4.jsx contents
# Add "import React from 'react';" at line 1
npm start
```

## Project Structure

```
├── strat_final_1.ipynb          # Main notebook: 5 filters + backtest + metrics
├── trading_dashboard_v4.jsx     # Live trading dashboard (React)
├── backtest_metrics.py          # Standalone metrics calculator
├── collect_btc_data_v2.py       # BTC data collector (Binance/Coinbase/Bybit)
├── collect_sand_data_v2.py      # SAND data collector (Binance/MEXC/Bybit)
├── spread_scanner.py            # Multi-coin spread scanner
└── README.md
```

## Key Findings

| Market | Avg Spread | Cost | Tradeable | Result |
|--------|-----------|------|-----------|--------|
| BTC (Binance/Coinbase/Bybit) | 1.82 bps | 24 bps | 0.007% | No trades |
| SAND (Binance/MEXC/Bybit) | 12.64 bps | 24 bps | 12.2% | Negative P&L (spreads don't mean-revert) |
| Synthetic (GBM) | 5–30 bps | 5–7 bps | 30–60% | Profitable (controlled environment) |

## Known Limitations

- **Execution bias**: Assumes fills at quoted prices
- **No market impact**: Orders don't move prices
- **Self-referencing z-score**: Current dislocation inflates the rolling window
- **No funding costs**: Short leg borrowing fees not modeled
- **No time-of-day effects**: Intraday patterns not captured
- **Synthetic data always mean-reverts**: Real markets don't guarantee this

## Future Work

- Ornstein-Uhlenbeck reversion predictor (estimate half-life before entry)
- Dynamic position sizing (signal confidence → trade size)
- Regime detection (Hurst exponent — only trade during mean-reverting periods)
- DEX vs CEX arbitrage (wider spreads on decentralized exchanges)
- Pairs trading on correlated assets (e.g., silver ETFs)

## License

MIT
