"""
Arbitrage Spread Scanner — Find Tradeable Coins
Scans multiple coins across Binance, Coinbase, and Bybit
to find which ones have spreads larger than trading costs.

INSTRUCTIONS:
  1. pip install requests
  2. python spread_scanner.py
  3. Wait 3-5 minutes
  4. It will tell you which coins have tradeable spreads

No API keys needed.
"""

import requests
import json
import time
from datetime import datetime, timedelta

print("=" * 65)
print("  ARBITRAGE SPREAD SCANNER")
print("  Scanning coins across Binance · Coinbase · Bybit")
print("=" * 65)

# ═══════════════════════════════════════════
# COINS TO SCAN
# ═══════════════════════════════════════════

COINS = [
    # Major (probably too efficient, but let's check)
    {"name": "ETH",  "binance": "ETHUSDT",  "coinbase": "ETH-USD",  "bybit": "ETHUSDT"},
    {"name": "SOL",  "binance": "SOLUSDT",  "coinbase": "SOL-USD",  "bybit": "SOLUSDT"},
    
    # Mid-cap (might have decent spreads)
    {"name": "DOGE", "binance": "DOGEUSDT", "coinbase": "DOGE-USD", "bybit": "DOGEUSDT"},
    {"name": "AVAX", "binance": "AVAXUSDT", "coinbase": "AVAX-USD", "bybit": "AVAXUSDT"},
    {"name": "LINK", "binance": "LINKUSDT", "coinbase": "LINK-USD", "bybit": "LINKUSDT"},
    {"name": "DOT",  "binance": "DOTUSDT",  "coinbase": "DOT-USD",  "bybit": "DOTUSDT"},
    {"name": "MATIC","binance": "MATICUSDT","coinbase": "MATIC-USD","bybit": "MATICUSDT"},
    {"name": "UNI",  "binance": "UNIUSDT",  "coinbase": "UNI-USD",  "bybit": "UNIUSDT"},
    
    # Smaller (best chance for wide spreads)
    {"name": "FET",  "binance": "FETUSDT",  "coinbase": "FET-USD",  "bybit": "FETUSDT"},
    {"name": "INJ",  "binance": "INJUSDT",  "coinbase": "INJ-USD",  "bybit": "INJUSDT"},
    {"name": "AAVE", "binance": "AAVEUSDT", "coinbase": "AAVE-USD", "bybit": "AAVEUSDT"},
    {"name": "CRV",  "binance": "CRVUSDT",  "coinbase": "CRV-USD",  "bybit": "CRVUSDT"},
    {"name": "NEAR", "binance": "NEARUSDT", "coinbase": "NEAR-USD", "bybit": "NEARUSDT"},
    {"name": "APE",  "binance": "APEUSDT",  "coinbase": "APE-USD",  "bybit": "APEUSDT"},
    {"name": "SAND", "binance": "SANDUSDT", "coinbase": "SAND-USD", "bybit": "SANDUSDT"},
    {"name": "MANA", "binance": "MANAUSDT", "coinbase": "MANA-USD", "bybit": "MANAUSDT"},
]

# How many minutes of data to sample per coin (more = slower but more accurate)
SAMPLE_MINUTES = 1000  # ~16 hours of data per coin

# Trading costs
FEE_PER_SIDE = 10  # 10 bps = 0.1%
SLIPPAGE = 2       # 2 bps per side
ROUND_TRIP_COST = FEE_PER_SIDE * 2 + SLIPPAGE * 2  # 24 bps

print(f"\n  Scanning {len(COINS)} coins")
print(f"  Sample: {SAMPLE_MINUTES} minutes per coin")
print(f"  Round-trip cost: {ROUND_TRIP_COST} bps")
print(f"  A coin is 'tradeable' if it has enough ticks with spread > {ROUND_TRIP_COST} bps\n")


# ═══════════════════════════════════════════
# FETCH FUNCTIONS
# ═══════════════════════════════════════════

def fetch_binance(symbol, start_ms, end_ms, limit=1000):
    url = "https://api.binance.com/api/v3/klines"
    all_data = {}
    current = start_ms
    while current < end_ms:
        try:
            r = requests.get(url, params={
                "symbol": symbol, "interval": "1m",
                "startTime": current, "endTime": end_ms, "limit": limit
            }, timeout=10)
            if r.status_code == 400:
                return None  # symbol doesn't exist
            r.raise_for_status()
            data = r.json()
            if not data: break
            for c in data:
                minute = (c[0] // 60000) * 60000
                all_data[minute] = float(c[4])
            current = data[-1][0] + 60000
            time.sleep(0.15)
        except Exception as e:
            return None
    return all_data


def fetch_coinbase(symbol, start_dt, end_dt):
    url = f"https://api.exchange.coinbase.com/products/{symbol}/candles"
    all_data = {}
    current_end = end_dt
    while current_end > start_dt:
        current_start = max(current_end - timedelta(minutes=300), start_dt)
        try:
            r = requests.get(url, params={
                "start": current_start.isoformat() + "Z",
                "end": current_end.isoformat() + "Z",
                "granularity": 60
            }, timeout=10)
            if r.status_code == 404:
                return None
            r.raise_for_status()
            data = r.json()
            if not data: break
            for c in data:
                minute = (c[0] * 1000 // 60000) * 60000
                all_data[minute] = float(c[4])
            current_end = current_start - timedelta(minutes=1)
            time.sleep(0.25)
        except:
            return None
    return all_data


def fetch_bybit(symbol, start_ms, end_ms):
    url = "https://api.bybit.com/v5/market/kline"
    all_data = {}
    current_end = end_ms
    while current_end > start_ms:
        try:
            r = requests.get(url, params={
                "category": "spot", "symbol": symbol,
                "interval": "1", "start": start_ms,
                "end": current_end, "limit": 1000
            }, timeout=10)
            r.raise_for_status()
            result = r.json()
            if result.get("retCode") != 0: return None
            data = result.get("result", {}).get("list", [])
            if not data: break
            for c in data:
                minute = (int(c[0]) // 60000) * 60000
                all_data[minute] = float(c[4])
            oldest = min(int(c[0]) for c in data)
            current_end = oldest - 60000
            time.sleep(0.15)
        except:
            return None
    return all_data


# ═══════════════════════════════════════════
# SCAN EACH COIN
# ═══════════════════════════════════════════

end_time = datetime.utcnow()
start_time = end_time - timedelta(minutes=SAMPLE_MINUTES)
start_ms = int(start_time.timestamp() * 1000)
end_ms = int(end_time.timestamp() * 1000)

results = []

for i, coin in enumerate(COINS):
    name = coin["name"]
    print(f"  [{i+1}/{len(COINS)}] Scanning {name}...", end="", flush=True)
    
    # Fetch from all 3 exchanges
    b_data = fetch_binance(coin["binance"], start_ms, end_ms)
    c_data = fetch_coinbase(coin["coinbase"], start_time, end_time)
    by_data = fetch_bybit(coin["bybit"], start_ms, end_ms)
    
    # Check which exchanges have data
    available = []
    if b_data and len(b_data) > 100: available.append(("Binance", b_data))
    if c_data and len(c_data) > 100: available.append(("Coinbase", c_data))
    if by_data and len(by_data) > 100: available.append(("Bybit", by_data))
    
    if len(available) < 2:
        print(f" ❌ only {len(available)} exchange(s) have data, need 2+")
        continue
    
    # Find common timestamps
    common = set(available[0][1].keys())
    for _, d in available[1:]:
        common &= set(d.keys())
    common = sorted(common)
    
    if len(common) < 100:
        print(f" ❌ only {len(common)} aligned ticks")
        continue
    
    # Compute spreads
    spreads = []
    for ts in common:
        prices = [d[ts] for _, d in available]
        mx, mn = max(prices), min(prices)
        mid = (mx + mn) / 2
        if mid > 0:
            s = (mx - mn) / mid * 10000
            spreads.append(s)
    
    if not spreads:
        print(f" ❌ no spread data")
        continue
    
    import numpy as np
    spreads = np.array(spreads)
    
    avg_spread = spreads.mean()
    median_spread = np.median(spreads)
    max_spread = spreads.max()
    pct_above_cost = (spreads > ROUND_TRIP_COST).sum() / len(spreads) * 100
    pct_above_10 = (spreads > 10).sum() / len(spreads) * 100
    pct_above_5 = (spreads > 5).sum() / len(spreads) * 100
    n_tradeable = (spreads > ROUND_TRIP_COST).sum()
    
    exchanges_str = "+".join([e[0] for e in available])
    
    result = {
        "name": name,
        "exchanges": exchanges_str,
        "n_ticks": len(common),
        "avg_spread": round(avg_spread, 2),
        "median_spread": round(median_spread, 2),
        "max_spread": round(max_spread, 1),
        "pct_above_5": round(pct_above_5, 1),
        "pct_above_10": round(pct_above_10, 1),
        "pct_above_cost": round(pct_above_cost, 1),
        "n_tradeable": n_tradeable,
        "tradeable": pct_above_cost > 1.0,  # at least 1% of ticks are tradeable
    }
    results.append(result)
    
    symbol = "✅" if result["tradeable"] else "❌"
    print(f" {symbol} avg={avg_spread:.1f}bps  max={max_spread:.0f}bps  >{ROUND_TRIP_COST}bps={pct_above_cost:.1f}%  ({len(common)} ticks, {exchanges_str})")


# ═══════════════════════════════════════════
# RESULTS SUMMARY
# ═══════════════════════════════════════════

print(f"\n{'='*65}")
print(f"  SCAN RESULTS — {len(results)} coins analyzed")
print(f"  Round-trip cost: {ROUND_TRIP_COST} bps (fee {FEE_PER_SIDE}bps/side + slip {SLIPPAGE}bps/side)")
print(f"{'='*65}\n")

# Sort by tradeability
results.sort(key=lambda x: x["pct_above_cost"], reverse=True)

print(f"  {'Coin':<6} {'Exchanges':<25} {'Ticks':>6} {'Avg':>6} {'Med':>6} {'Max':>6} {'>5bps':>6} {'>10bp':>6} {f'>{ROUND_TRIP_COST}bp':>6} {'Trade?':>7}")
print(f"  {'-'*92}")

for r in results:
    symbol = "✅ YES" if r["tradeable"] else "❌ NO"
    print(f"  {r['name']:<6} {r['exchanges']:<25} {r['n_ticks']:>6,} {r['avg_spread']:>6.1f} {r['median_spread']:>6.1f} {r['max_spread']:>6.0f} {r['pct_above_5']:>5.1f}% {r['pct_above_10']:>5.1f}% {r['pct_above_cost']:>5.1f}% {symbol:>7}")

tradeable = [r for r in results if r["tradeable"]]
print(f"\n  TRADEABLE COINS: {len(tradeable)}/{len(results)}")

if tradeable:
    print(f"\n  🎯 Best candidates for our arbitrage engine:")
    for r in tradeable[:5]:
        print(f"    {r['name']:>5} — avg spread {r['avg_spread']:.1f} bps, "
              f"{r['pct_above_cost']:.1f}% of ticks above cost, "
              f"max spread {r['max_spread']:.0f} bps")
    
    print(f"\n  To collect full data for the best coin, run:")
    best = tradeable[0]
    print(f"    → Modify collect_btc_data_v2.py to use {best['name']} symbols")
    print(f"    → Collect 30K ticks")
    print(f"    → Upload to Claude and run the full pipeline")
else:
    print(f"\n  ⚠️  No coins found with enough spread to cover {ROUND_TRIP_COST} bps costs.")
    print(f"      Options:")
    print(f"        1. Try smaller exchanges (MEXC, Gate.io, KuCoin) instead of Coinbase")
    print(f"        2. Try even smaller coins (micro-caps)")
    print(f"        3. Try DEX vs CEX arbitrage (Uniswap vs Binance)")
    print(f"        4. Reduce fees with VIP/maker tiers")

# Save results
with open("spread_scan_results.json", "w") as f:
    json.dump(results, f, indent=2)
print(f"\n  💾 Saved spread_scan_results.json")
print(f"{'='*65}")
