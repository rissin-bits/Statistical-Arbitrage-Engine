"""
SAND Historical Data Collector — Binance, MEXC, Bybit
Fetches 30,000 aligned 1-minute candle close prices for SAND.

INSTRUCTIONS:
  1. pip install requests
  2. python collect_sand_data_v2.py
  3. Upload 'sand_30k.json' to Claude
"""

import requests
import json
import time
from datetime import datetime, timedelta

print("=" * 65)
print("  SAND Data Collector — Binance · MEXC · Bybit")
print("  Fetching 30,000 aligned 1-minute ticks")
print("=" * 65)

TOTAL_TICKS = 30000
end_time = datetime.utcnow()
start_time = end_time - timedelta(minutes=TOTAL_TICKS)
start_ms = int(start_time.timestamp() * 1000)
end_ms = int(end_time.timestamp() * 1000)

print(f"\n  Period: {start_time.strftime('%Y-%m-%d %H:%M')} → {end_time.strftime('%Y-%m-%d %H:%M')} UTC")


# ═══════════════════════════════════════════
# BINANCE — SAND/USDT
# ═══════════════════════════════════════════

def fetch_binance(start_ms, end_ms):
    url = "https://api.binance.com/api/v3/klines"
    all_data = {}
    current = start_ms
    batches = 0
    while current < end_ms:
        try:
            r = requests.get(url, params={"symbol":"SANDUSDT","interval":"1m","startTime":current,"endTime":end_ms,"limit":1000}, timeout=15)
            r.raise_for_status()
            data = r.json()
            if not data: break
            for c in data:
                all_data[(c[0]//60000)*60000] = float(c[4])
            current = data[-1][0] + 60000
            batches += 1
            if batches % 10 == 0: print(f"    ... {len(all_data):,} candles")
            time.sleep(0.2)
        except Exception as e:
            print(f"    Binance error: {e}, retrying...")
            time.sleep(2)
    return all_data


# ═══════════════════════════════════════════
# MEXC — SAND/USDT
# ═══════════════════════════════════════════

def fetch_mexc(start_ms, end_ms):
    url = "https://api.mexc.com/api/v3/klines"
    all_data = {}
    current = start_ms
    batches = 0
    while current < end_ms:
        try:
            r = requests.get(url, params={"symbol":"SANDUSDT","interval":"1m","startTime":current,"endTime":end_ms,"limit":1000}, timeout=15)
            r.raise_for_status()
            data = r.json()
            if not data: break
            for c in data:
                all_data[(c[0]//60000)*60000] = float(c[4])
            current = data[-1][0] + 60000
            batches += 1
            if batches % 10 == 0: print(f"    ... {len(all_data):,} candles")
            time.sleep(0.2)
        except Exception as e:
            print(f"    MEXC error: {e}, retrying...")
            time.sleep(2)
    return all_data


# ═══════════════════════════════════════════
# BYBIT — SAND/USDT
# ═══════════════════════════════════════════

def fetch_bybit(start_ms, end_ms):
    url = "https://api.bybit.com/v5/market/kline"
    all_data = {}
    current_end = end_ms
    batches = 0
    while current_end > start_ms:
        try:
            r = requests.get(url, params={"category":"spot","symbol":"SANDUSDT","interval":"1","start":start_ms,"end":current_end,"limit":1000}, timeout=15)
            r.raise_for_status()
            result = r.json()
            if result.get("retCode") != 0: break
            data = result.get("result",{}).get("list",[])
            if not data: break
            for c in data:
                ts = (int(c[0])//60000)*60000
                if ts >= start_ms: all_data[ts] = float(c[4])
            oldest = min(int(c[0]) for c in data)
            current_end = oldest - 60000
            batches += 1
            if batches % 10 == 0: print(f"    ... {len(all_data):,} candles")
            time.sleep(0.2)
        except Exception as e:
            print(f"    Bybit error: {e}, retrying...")
            time.sleep(2)
    return all_data


# ═══════════════════════════════════════════
# FETCH ALL
# ═══════════════════════════════════════════

print(f"\n  Fetching Binance SAND/USDT...")
binance = fetch_binance(start_ms, end_ms)
print(f"    ✅ {len(binance):,} candles")

print(f"\n  Fetching MEXC SAND/USDT...")
mexc = fetch_mexc(start_ms, end_ms)
print(f"    ✅ {len(mexc):,} candles")

print(f"\n  Fetching Bybit SAND/USDT...")
bybit = fetch_bybit(start_ms, end_ms)
print(f"    ✅ {len(bybit):,} candles")


# ═══════════════════════════════════════════
# ALIGN
# ═══════════════════════════════════════════

print(f"\n  Aligning timestamps...")
print(f"    Binance : {len(binance):,}")
print(f"    MEXC    : {len(mexc):,}")
print(f"    Bybit   : {len(bybit):,}")

# Try all 3
common_3 = sorted(set(binance.keys()) & set(mexc.keys()) & set(bybit.keys()))
print(f"    All 3 aligned   : {len(common_3):,}")

# Try pairs
common_bm = sorted(set(binance.keys()) & set(mexc.keys()))
common_bb = sorted(set(binance.keys()) & set(bybit.keys()))
common_mb = sorted(set(mexc.keys()) & set(bybit.keys()))
print(f"    Binance+MEXC    : {len(common_bm):,}")
print(f"    Binance+Bybit   : {len(common_bb):,}")
print(f"    MEXC+Bybit      : {len(common_mb):,}")

# Use whichever gives the most ticks
options = [
    (common_3, ["Binance","MEXC","Bybit"], {"binance":binance,"mexc":mexc,"bybit":bybit}),
    (common_bm, ["Binance","MEXC"], {"binance":binance,"mexc":mexc}),
    (common_bb, ["Binance","Bybit"], {"binance":binance,"bybit":bybit}),
    (common_mb, ["MEXC","Bybit"], {"mexc":mexc,"bybit":bybit}),
]

# Prefer 3 exchanges if enough data, otherwise pick the pair with most ticks
best_option = None
for ts_list, exchs, dicts in options:
    if len(exchs) == 3 and len(ts_list) >= 10000:
        best_option = (ts_list, exchs, dicts)
        break

if best_option is None:
    # Pick the option with the most ticks
    options.sort(key=lambda x: len(x[0]), reverse=True)
    best_option = options[0]

use_ts, use_exchs, use_dicts = best_option
use_ts = use_ts[:TOTAL_TICKS]
n = len(use_ts)

print(f"\n  ✅ Using: {' + '.join(use_exchs)} ({n:,} ticks)")

# Build output
output = {"timestamps": [t//1000 for t in use_ts], "n_ticks": n,
          "interval": "1m", "pair": "SAND/USDT", "exchanges": use_exchs}
for exch in use_exchs:
    key = exch.lower()
    output[key] = [round(use_dicts[key][t], 6) for t in use_ts]


# ═══════════════════════════════════════════
# ANALYSIS
# ═══════════════════════════════════════════

import numpy as np

print(f"\n  ── DATA SUMMARY ──")
print(f"  Ticks     : {n:,}")
print(f"  Exchanges : {use_exchs}")

if n > 0:
    ts = output["timestamps"]
    print(f"  Time      : {datetime.utcfromtimestamp(ts[0]).strftime('%Y-%m-%d %H:%M')} → "
          f"{datetime.utcfromtimestamp(ts[-1]).strftime('%Y-%m-%d %H:%M')} UTC")
    
    for exch in use_exchs:
        prices = output[exch.lower()]
        print(f"  {exch:<10s}: ${min(prices):.4f} — ${max(prices):.4f}")
    
    spreads = []
    for i in range(n):
        prices = [output[e.lower()][i] for e in use_exchs]
        mx, mn = max(prices), min(prices)
        mid = (mx+mn)/2
        if mid > 0: spreads.append((mx-mn)/mid*10000)
    spreads = np.array(spreads)
    
    cost = 24
    print(f"\n  ── SPREAD ANALYSIS ──")
    print(f"  Avg spread    : {spreads.mean():.2f} bps")
    print(f"  Median spread : {np.median(spreads):.2f} bps")
    print(f"  Max spread    : {spreads.max():.1f} bps")
    
    for thresh in [5, 10, 15, 20, 24, 30, 50]:
        c = (spreads>thresh).sum()
        print(f"  > {thresh:>2} bps     : {c:>6,} ({c/n*100:>5.1f}%)")
    
    tradeable = (spreads>cost).sum()
    print(f"\n  Tradeable (>{cost}bps): {tradeable:,} ({tradeable/n*100:.1f}%)")
    
    train_n = min(10000, n//3)
    print(f"\n  ── SPLIT ──")
    print(f"  Training : {train_n:,} ticks")
    print(f"  Live     : {n-train_n:,} ticks")

# Save
filename = "sand_30k.json"
with open(filename, "w") as f:
    json.dump(output, f)
print(f"\n  💾 Saved to {filename} ({len(json.dumps(output))//1024} KB)")
print(f"\n  Upload {filename} to Claude to run the full pipeline.")
print(f"{'='*65}")
