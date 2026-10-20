#!/usr/bin/env python3
"""Fetch UK share quotes, calculate daily moves, and optionally summarise with local Ollama."""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import yfinance as yf

ROOT = Path(__file__).resolve().parents[1]
WATCHLIST = ROOT / "config" / "stocks.json"
LATEST_FILE = ROOT / "data" / "latest.json"
HISTORY_FILE = ROOT / "data" / "history.json"
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434/api/generate")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "granite4:3b")
LONDON_TZ = ZoneInfo("Europe/London")


def read_json(path: Path, fallback):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return fallback


def local_timestamp() -> str:
    return datetime.now(LONDON_TZ).isoformat(timespec="seconds")


def fetch_stock(item: dict) -> dict:
    ticker_symbol = item["ticker"]
    result = {
        "ticker": ticker_symbol,
        "name": item["name"],
        "sector": item.get("sector", "Technology"),
        "price_gbp": None,
        "change_pct": None,
        "previous_close_gbp": None,
        "quote_date": None,
        "status": "unavailable",
        "error": None,
    }
    try:
        ticker = yf.Ticker(ticker_symbol)
        history = ticker.history(period="7d", interval="1d", auto_adjust=False, actions=False)
        if history.empty or len(history) < 1:
            raise ValueError("No daily price rows returned")
        closes = history["Close"].dropna()
        if closes.empty:
            raise ValueError("No closing prices returned")
        latest_close = float(closes.iloc[-1])
        previous_close = float(closes.iloc[-2]) if len(closes) > 1 else None

        currency = ""
        try:
            currency = str(ticker.fast_info.get("currency", "") or "")
        except Exception:
            try:
                currency = str(ticker.info.get("currency", "") or "")
            except Exception:
                currency = ""

        # Yahoo commonly expresses London Stock Exchange prices in GBp (pence).
        divisor = 100.0 if currency.lower() in {"gbp", "gbpence", "gbp pence", "gbpence"} and ticker_symbol.endswith(".L") else 1.0
        # Yahoo's currency code for pence is commonly GBp; GBP means pounds.
        if currency == "GBp" and ticker_symbol.endswith(".L"):
            divisor = 100.0
        elif currency == "GBP":
            divisor = 1.0

        price_gbp = latest_close / divisor
        previous_gbp = previous_close / divisor if previous_close is not None else None
        change_pct = None
        if previous_gbp not in (None, 0):
            change_pct = ((price_gbp - previous_gbp) / previous_gbp) * 100.0

        last_index = closes.index[-1]
        quote_date = last_index.strftime("%Y-%m-%d")
        result.update({
            "price_gbp": round(price_gbp, 4),
            "previous_close_gbp": round(previous_gbp, 4) if previous_gbp is not None else None,
            "change_pct": round(change_pct, 3) if change_pct is not None else None,
            "quote_date": quote_date,
            "currency_source": currency or "unknown",
            "status": "ok",
            "error": None,
        })
    except Exception as exc:
        result["error"] = str(exc)[:240]
        print(f"[WARN] {ticker_symbol}: {result['error']}", file=sys.stderr)
    return result


def granite_summary(stocks: list[dict]) -> tuple[str, str]:
    valid = [s for s in stocks if s["status"] == "ok" and s["change_pct"] is not None]
    if not valid:
        return "No verified daily price changes were available for a market summary.", "Python fallback"

    movers = sorted(valid, key=lambda s: s["change_pct"])
    facts = [
        {"ticker": s["ticker"], "company": s["name"], "price_gbp": s["price_gbp"], "daily_change_pct": s["change_pct"]}
        for s in valid
    ]
    prompt = (
        "Write a concise UK technology-share market briefing in 3 short bullet points. "
        "Use only the JSON facts supplied. Mention the strongest riser and faller if clear. "
        "Do not invent facts, causes, news, forecasts, or prices. Do not recommend buying or selling. "
        "Say that this is a watchlist snapshot, not investment advice. JSON facts: "
        + json.dumps(facts, ensure_ascii=False)
    )
    payload = json.dumps({
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.2, "num_predict": 220},
    }).encode("utf-8")
    request = urllib.request.Request(
        OLLAMA_URL,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            result = json.loads(response.read().decode("utf-8"))
        summary = str(result.get("response", "")).strip()
        if summary:
            return summary, "Local Ollama model: " + OLLAMA_MODEL
        raise ValueError("Ollama returned an empty summary")
    except (urllib.error.URLError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
        return (
            "Local Granite summary unavailable for this run. Price movements below were calculated by Python. "
            "Check that Ollama is running and the model '" + OLLAMA_MODEL + "' is installed. "
            "No AI-generated market interpretation has been substituted.",
            "Python fallback (" + str(exc)[:100] + ")",
        )


def main() -> int:
    watchlist = read_json(WATCHLIST, [])
    if not watchlist:
        print(f"Watchlist is missing or empty: {WATCHLIST}", file=sys.stderr)
        return 1

    print(f"Fetching daily prices for {len(watchlist)} UK-listed shares...")
    stocks = [fetch_stock(item) for item in watchlist]
    successful = sum(1 for s in stocks if s["status"] == "ok")
    if successful == 0:
        print("No quotes were retrieved. Keeping existing dashboard data unchanged.", file=sys.stderr)
        return 1

    summary, summary_source = granite_summary(stocks)
    timestamp = local_timestamp()
    payload = {
        "status": "ok",
        "updated_at": timestamp,
        "market": "London Stock Exchange",
        "ai_summary": summary,
        "summary_source": summary_source,
        "note": f"{successful} of {len(stocks)} quotes retrieved. Prices are daily closing data and may be delayed. Not investment advice.",
        "stocks": stocks,
    }
    LATEST_FILE.parent.mkdir(parents=True, exist_ok=True)
    LATEST_FILE.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    history = read_json(HISTORY_FILE, [])
    if not isinstance(history, list):
        history = []
    snapshot_date = datetime.now(LONDON_TZ).date().isoformat()
    history_entry = {
        "date": snapshot_date,
        "updated_at": timestamp,
        "stocks": [
            {"ticker": s["ticker"], "name": s["name"], "price_gbp": s["price_gbp"], "change_pct": s["change_pct"]}
            for s in stocks if s["status"] == "ok"
        ],
    }
    # Replace the same day's snapshot if this script is run more than once.
    history = [entry for entry in history if entry.get("date") != snapshot_date]
    history.append(history_entry)
    history.sort(key=lambda entry: entry.get("date", ""))
    HISTORY_FILE.write_text(json.dumps(history, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(f"Completed: {successful}/{len(stocks)} quotes; updated {LATEST_FILE.relative_to(ROOT)}")
    print(f"Granite summary source: {summary_source}")
    print(summary)
    print("Next: review data/latest.json, then commit and push data/latest.json and data/history.json.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
