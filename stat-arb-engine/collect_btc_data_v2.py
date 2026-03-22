"""
BTC Historical Data Collector — Binance, Coinbase, Bybit
Fetches 30,000 aligned 1-minute candle close prices.

INSTRUCTIONS:
  1. pip install requests
  2. python collect_btc_data_v2.py
  3. Upload the generated 'btc_30k.json' file to Claude
"""

import requests
import json
import time
from datetime import datetime, timedelta

print("=" * 60)
print("  BTC Data Collector — Binance · Coinbase · Bybit")
print("  Fetching 30,000 aligned 1-minute ticks")
print("=" * 60)

TOTAL_TICKS = 30000
end_time = datetime.utcnow()
start_time = end_time - timedelta(minutes=TOTAL_TICKS)

print(f"\n  Period: {start_time.strftime('%Y-%m-%d %H:%M')} → {end_time.strftime('%Y-%m-%d %H:%M')} UTC")


# ═══════════════════════════════════════════
# BINANCE — BTC/USDT 1m klines
# ═══════════════════════════════════════════

def fetch_binance(start_ms, end_ms):
    url = "https://api.binance.com/api/v3/klines"
    all_data = []
    current = start_ms
    while current < end_ms:
        params = {"symbol":"BTCUSDT","interval":"1m","startTime":current,"endTime":end_ms,"limit":1000}
        try:
            r = requests.get(url, params=params, timeout=15)
            r.raise_for_status()
            data = r.json()
            if not data: break
            for c in data:
                all_data.append((c[0], float(c[4])))
            current = data[-1][0] + 60000
            time.sleep(0.2)
        except Exception as e:
            print(f"    Binance error: {e}, retrying...")
            time.sleep(2)
    return all_data


# ═══════════════════════════════════════════
# COINBASE — BTC/USD 1m candles
# ═══════════════════════════════════════════

def fetch_coinbase(start_dt, end_dt):
    url = "https://api.exchange.coinbase.com/products/BTC-USD/candles"
    all_data = []
    current_end = end_dt
    while current_end > start_dt:
        current_start = max(current_end - timedelta(minutes=300), start_dt)
        params = {"start":current_start.isoformat()+"Z","end":current_end.isoformat()+"Z","granularity":60}
        try:
            r = requests.get(url, params=params, timeout=15)
            r.raise_for_status()
            data = r.json()
            if not data: break
            for c in data:
                all_data.append((c[0]*1000, float(c[4])))
            current_end = current_start - timedelta(minutes=1)
            time.sleep(0.3)
        except Exception as e:
            print(f"    Coinbase error: {e}, retrying...")
            time.sleep(2)
    return all_data


# ═══════════════════════════════════════════
# BYBIT — BTC/USDT 1m klines
# ═══════════════════════════════════════════

def fetch_bybit(start_ms, end_ms):
    url = "https://api.bybit.com/v5/market/kline"
    all_data = []
    current_end = end_ms
    
    while current_end > start_ms:
        params = {
            "category": "spot",
            "symbol": "BTCUSDT",
            "interval": "1",
            "start": start_ms,
            "end": current_end,
            "limit": 1000,
        }
        try:
            r = requests.get(url, params=params, timeout=15)
            r.raise_for_status()
            result = r.json()
            
            if result.get("retCode") != 0:
                print(f"    Bybit API error: {result.get('retMsg')}")
                break
            
            data = result.get("result", {}).get("list", [])
            if not data:
                break
            
            for c in data:
                # [startTime, open, high, low, close, volume, turnover]
                ts = int(c[0])
                close = float(c[4])
                if ts >= start_ms:
                    all_data.append((ts, close))
            
            # Bybit returns newest first, so oldest timestamp is last
            oldest = min(int(c[0]) for c in data)
            current_end = oldest - 60000
            time.sleep(0.2)
            
        except Exception as e:
            print(f"    Bybit error: {e}, retrying...")
            time.sleep(2)
    
    return all_data


# ═══════════════════════════════════════════
# FETCH ALL
# ═══════════════════════════════════════════

start_ms = int(start_time.timestamp() * 1000)
end_ms = int(end_time.timestamp() * 1000)

print(f"\n  Fetching Binance BTC/USDT...")
binance_raw = fetch_binance(start_ms, end_ms)
print(f"    Got {len(binance_raw):,} candles")

print(f"\n  Fetching Coinbase BTC/USD...")
coinbase_raw = fetch_coinbase(start_time, end_time)
print(f"    Got {len(coinbase_raw):,} candles")

print(f"\n  Fetching Bybit BTC/USDT...")
bybit_raw = fetch_bybit(start_ms, end_ms)
print(f"    Got {len(bybit_raw):,} candles")


# ═══════════════════════════════════════════
# ALIGN BY TIMESTAMP
# ═══════════════════════════════════════════

print(f"\n  Aligning timestamps...")

def to_minute_dict(raw_data):
    d = {}
    for ts_ms, price in raw_data:
        minute = (ts_ms // 60000) * 60000
        d[minute] = price
    return d

binance_dict = to_minute_dict(binance_raw)
coinbase_dict = to_minute_dict(coinbase_raw)
bybit_dict = to_minute_dict(bybit_raw)

common_ts = sorted(
    set(binance_dict.keys()) &
    set(coinbase_dict.keys()) &
    set(bybit_dict.keys())
)

print(f"    Binance  : {len(binance_dict):,} minutes")
print(f"    Coinbase : {len(coinbase_dict):,} minutes")
print(f"    Bybit    : {len(bybit_dict):,} minutes")
print(f"    Aligned  : {len(common_ts):,} minutes")

if len(common_ts) < TOTAL_TICKS:
    print(f"\n  ⚠️  {len(common_ts):,} aligned ticks available (wanted {TOTAL_TICKS:,})")

use_ts = common_ts[:TOTAL_TICKS]
n = len(use_ts)

binance_prices = [round(binance_dict[t], 2) for t in use_ts]
coinbase_prices = [round(coinbase_dict[t], 2) for t in use_ts]
bybit_prices = [round(bybit_dict[t], 2) for t in use_ts]
timestamps = [t // 1000 for t in use_ts]


# ═══════════════════════════════════════════
# ANALYSIS
# ═══════════════════════════════════════════

print(f"\n  ── DATA SUMMARY ──")
print(f"  Total aligned ticks: {n:,}")

if n > 0:
    print(f"  Time: {datetime.utcfromtimestamp(timestamps[0]).strftime('%Y-%m-%d %H:%M')} → "
          f"{datetime.utcfromtimestamp(timestamps[-1]).strftime('%Y-%m-%d %H:%M')} UTC")
    print(f"  Binance  : ${min(binance_prices):,.2f} — ${max(binance_prices):,.2f}")
    print(f"  Coinbase : ${min(coinbase_prices):,.2f} — ${max(coinbase_prices):,.2f}")
    print(f"  Bybit    : ${min(bybit_prices):,.2f} — ${max(bybit_prices):,.2f}")

    count_5 = count_10 = count_20 = 0
    max_spread = 0
    spreads = []

    for i in range(n):
        mx = max(binance_prices[i], coinbase_prices[i], bybit_prices[i])
        mn = min(binance_prices[i], coinbase_prices[i], bybit_prices[i])
        mid = (mx + mn) / 2
        s = (mx - mn) / mid * 10000
        spreads.append(s)
        max_spread = max(max_spread, s)
        if s > 5: count_5 += 1
        if s > 10: count_10 += 1
        if s > 20: count_20 += 1

    avg_spread = sum(spreads) / len(spreads)

    print(f"\n  ── SPREAD ANALYSIS ──")
    print(f"  Avg spread               : {avg_spread:.2f} bps")
    print(f"  Max spread               : {max_spread:.1f} bps")
    print(f"  Ticks with spread > 5 bps  : {count_5:,} ({count_5/n*100:.1f}%)")
    print(f"  Ticks with spread > 10 bps : {count_10:,} ({count_10/n*100:.1f}%)")
    print(f"  Ticks with spread > 20 bps : {count_20:,} ({count_20/n*100:.1f}%)")

    train_n = min(10000, n // 3)
    live_n = n - train_n
    print(f"\n  ── SPLIT ──")
    print(f"  Training : {train_n:,} ticks")
    print(f"  Live     : {live_n:,} ticks")


# ═══════════════════════════════════════════
# EXPORT
# ═══════════════════════════════════════════

output = {
    "binance": binance_prices,
    "coinbase": coinbase_prices,
    "bybit": bybit_prices,
    "timestamps": timestamps,
    "n_ticks": n,
    "interval": "1m",
    "pair": "BTC/USD",
    "exchanges": ["Binance", "Coinbase", "Bybit"],
}

filename = "btc_30k.json"
with open(filename, "w") as f:
    json.dump(output, f)

print(f"\n  💾 Saved to {filename} ({len(json.dumps(output))//1024} KB)")
print(f"\n  Upload {filename} to Claude to run the full pipeline.")
print(f"{'='*60}")
