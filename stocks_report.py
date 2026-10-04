#!/usr/bin/env python3
"""Stock watchlist report + price alarms. Sends to Telegram when env vars set."""
import json
import os
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import yaml
import yfinance as yf

HERE = Path(__file__).resolve().parent


def load_watchlist():
    data = yaml.safe_load((HERE / "watchlist.yaml").read_text()) or {}
    groups = data.get("watchlist") or data
    if not isinstance(groups, dict) or not groups:
        raise SystemExit("watchlist.yaml missing or empty")
    return {
        section: [(t["name"], t["symbol"]) for t in items]
        for section, items in groups.items()
    }


def format_line(name, price, d1, d7, d30):
    d30_val = d30 if d30 is not None else 0.0
    trend = "🟢" if d30_val >= 0 else "🔴"
    price_fmt = f"{price:.2f}"
    d7_val = d7 if d7 is not None else 0.0
    return f"[{name}]: {price_fmt} | 1D: {d1:+.2f}% | 7D: {d7_val:+.2f}% | 30D: {d30_val:+.2f}% | {trend}"


def get_change(hist, period_days):
    if hist is None or hist.empty or len(hist) < 2:
        return None
    closes = hist["Close"].dropna()
    if len(closes) < 2:
        return None
    first_close = closes.iloc[0]
    last_close = closes.iloc[-1]
    if first_close and first_close != 0:
        return ((last_close - first_close) / first_close) * 100
    return None


def last_price(symbol):
    hist = yf.Ticker(symbol).history(period="5d")
    if hist is None or hist.empty:
        return None
    closes = hist["Close"].dropna()
    if closes.empty:
        return None
    return float(closes.iloc[-1])


def send_telegram(text):
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        return False
    data = urllib.parse.urlencode({"chat_id": chat_id, "text": text}).encode()
    req = urllib.request.Request(f"https://api.telegram.org/bot{token}/sendMessage", data=data)
    with urllib.request.urlopen(req, timeout=30) as resp:
        resp.read()
    return True


def report():
    lines = []
    today = datetime.now(timezone.utc).strftime("%A, %B %d, %Y")
    lines.append(f"GitHub Stock Watchlist — {today}")
    lines.append("")

    errors = []

    for section, ticker_list in load_watchlist().items():
        lines.append(f"**{section}**")
        for name, symbol in ticker_list:
            try:
                hist = yf.Ticker(symbol).history(period="1mo")
                if hist is None or hist.empty:
                    errors.append(f"  {name} ({symbol}): No data returned")
                    continue
                closes = hist["Close"].dropna()
                if len(closes) < 2:
                    errors.append(f"  {name} ({symbol}): Insufficient data")
                    continue
                price = closes.iloc[-1]
                prev_close = closes.iloc[-2]
                d1 = ((price - prev_close) / prev_close) * 100 if prev_close else 0.0
                d7 = get_change(hist.iloc[-8:], 7) if len(hist) >= 8 else None
                d30 = get_change(hist, 30)
                lines.append(format_line(name, price, d1, d7, d30))
            except Exception as e:
                errors.append(f"  {name} ({symbol}): {e}")
        lines.append("")

    if errors:
        lines.append("---")
        lines.append("**Unavailable:**")
        lines.extend(errors)

    text = "\n".join(lines)
    print(text)
    send_telegram(text.replace("**", ""))


def load_targets():
    path = HERE / "targets.yaml"
    if not path.exists():
        return []
    data = yaml.safe_load(path.read_text()) or {}
    return data.get("targets") or []


def check_alerts():
    targets = load_targets()
    state_path = HERE / "state.json"
    state = {}
    if state_path.exists():
        state = json.loads(state_path.read_text() or "{}")

    msgs = []
    changed = False
    seen = set()
    for t in targets:
        symbol = t.get("symbol")
        if not symbol or symbol in seen:
            continue
        seen.add(symbol)
        name = t.get("name", symbol)
        try:
            price = last_price(symbol)
        except Exception as e:
            print(f"fetch failed: {name} ({symbol}): {e}")
            continue
        if price is None:
            print(f"no price: {name} ({symbol})")
            continue
        for side in ("above", "below"):
            limit = t.get(side)
            if limit is None:
                continue
            hit = price >= limit if side == "above" else price <= limit
            key = f"{symbol}:{side}:{limit}"
            armed = state.get(key, False)
            if hit and not armed:
                arrow = "▲" if side == "above" else "▼"
                msgs.append(f"🚨 ALARM {name}: {side} {limit:g} {arrow} — now {price:.2f}")
                state[key] = True
                changed = True
            elif not hit and armed:
                state[key] = False
                changed = True

    if changed:
        state_path.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n")
    if msgs:
        text = "\n".join(msgs)
        print(text)
        send_telegram(text)
    else:
        print("no alarms")


if __name__ == "__main__":
    if "--alerts" in sys.argv:
        check_alerts()
    else:
        report()
