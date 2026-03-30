"""
Agent 16 — Execution Gate API
==============================
Pre-trade guardrail for AI trading agents.

Aggregates 5 live signals and returns a single GO / NO-GO / WAIT verdict
before any buy or sell is executed. Acts as the final safety check in any
automated trading pipeline.

Signals evaluated per request:
  1. Sentiment     — crypto/stock news sentiment score (Agent 4a/4b)
  2. Fear & Greed  — composite market emotion index (Agent 4i)
  3. Macro         — risk-on / risk-off environment (Agent 4d)
  4. Whale         — accumulation / distribution pressure (Agent 4e)
  5. Volatility    — local price volatility classification

Verdict logic:
  GO      — 4+ signals align with proposed action (high confidence)
  WAIT    — 2-3 signals align (mixed — try again in 15 min)
  NO-GO   — 0-1 signals align (conflicting / dangerous)

Price: $0.010 USDC per call (x402 on Base)
Free:  20 calls per IP

Railway deploy: railway up
"""

import os
import time
import hashlib
import requests
from flask import Flask, request, jsonify
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed

app = Flask(__name__)

# ── Agent URLs ────────────────────────────────────────────────────────────────

SENTIMENT_URL  = os.getenv("SENTIMENT_URL",  "https://crypto-sentiment-api-production.up.railway.app")
FEAR_GREED_URL = os.getenv("FEAR_GREED_URL", "https://fear-greed-api-production.up.railway.app")
MACRO_URL      = os.getenv("MACRO_URL",      "https://macro-signal-api-production.up.railway.app")
WHALE_URL      = os.getenv("WHALE_URL",      "https://whale-monitor-api-production.up.railway.app")

# ── Payment config ────────────────────────────────────────────────────────────

CALL_COST_USD    = float(os.getenv("CALL_COST_USD", "0.010"))
FREE_CALLS_PER_IP = int(os.getenv("FREE_CALLS_PER_IP", "20"))
PAYMENT_ENABLED  = os.getenv("PAYMENT_ENABLED", "false").lower() == "true"

# ── In-memory counters ────────────────────────────────────────────────────────

call_log: dict[str, int] = {}   # ip_hash → call count
total_calls = 0
total_paid_calls = 0
start_time = time.time()

SUPPORTED_CRYPTO  = ["BTC", "ETH", "SOL", "BNB", "XRP", "DOGE", "ADA", "AVAX", "MATIC", "LINK"]
SUPPORTED_STOCKS  = ["PLTR", "TSLA", "NVDA", "ORCL", "MSFT", "GOOG", "META", "AMZN", "AAPL", "COIN", "IREN"]
SUPPORTED_ACTIONS = ["buy", "sell", "hold"]

# ── Signal fetchers ───────────────────────────────────────────────────────────

def fetch_sentiment(ticker: str, asset_type: str) -> dict:
    """Fetch news sentiment score for ticker."""
    try:
        base = SENTIMENT_URL
        r = requests.get(f"{base}/sentiment", params={"ticker": ticker}, timeout=6)
        if r.status_code == 200:
            d = r.json()
            return {
                "signal": "sentiment",
                "score": d.get("score", 50),
                "trend": d.get("trend", "neutral"),
                "confidence": d.get("confidence", "low"),
                "ok": True
            }
    except Exception as e:
        pass
    return {"signal": "sentiment", "ok": False, "error": "unavailable"}


def fetch_fear_greed(ticker: str) -> dict:
    """Fetch composite fear & greed index."""
    asset = ticker if ticker in SUPPORTED_CRYPTO else "BTC"
    try:
        r = requests.get(f"{FEAR_GREED_URL}/signal", params={"asset": asset}, timeout=6)
        if r.status_code == 200:
            d = r.json()
            return {
                "signal": "fear_greed",
                "score": d.get("score", 50),
                "classification": d.get("classification", "Neutral"),
                "action": d.get("signal", "HOLD"),
                "ok": True
            }
    except Exception:
        pass
    return {"signal": "fear_greed", "ok": False, "error": "unavailable"}


def fetch_macro() -> dict:
    """Fetch macro risk-on / risk-off signal."""
    try:
        r = requests.get(f"{MACRO_URL}/snapshot", timeout=6)
        if r.status_code == 200:
            d = r.json()
            return {
                "signal": "macro",
                "environment": d.get("macro_environment", "unknown"),
                "macro_score": d.get("macro_score", 50),
                "signal_text": d.get("macro_signal", ""),
                "ok": True
            }
    except Exception:
        pass
    return {"signal": "macro", "ok": False, "error": "unavailable"}


def fetch_whale(ticker: str) -> dict:
    """Fetch whale accumulation / distribution signal."""
    asset = ticker if ticker in ["BTC", "ETH"] else "BTC"
    try:
        r = requests.get(f"{WHALE_URL}/signal", params={"asset": asset}, timeout=6)
        if r.status_code == 200:
            d = r.json()
            return {
                "signal": "whale",
                "verdict": d.get("signal", "neutral"),
                "interpretation": d.get("interpretation", ""),
                "ok": True
            }
    except Exception:
        pass
    return {"signal": "whale", "ok": False, "error": "unavailable"}


def compute_local_volatility(ticker: str) -> dict:
    """
    Compute a simple volatility classification from CoinGecko price data.
    Uses 24h price change percentage as a proxy for near-term volatility.
    Falls back gracefully if CoinGecko is unavailable.
    """
    COIN_IDS = {
        "BTC": "bitcoin", "ETH": "ethereum", "SOL": "solana",
        "BNB": "binancecoin", "XRP": "ripple", "DOGE": "dogecoin",
        "ADA": "cardano", "AVAX": "avalanche-2", "MATIC": "matic-network",
        "LINK": "chainlink"
    }
    coin_id = COIN_IDS.get(ticker)
    if not coin_id:
        return {"signal": "volatility", "level": "unknown", "change_24h": None, "ok": False}

    try:
        r = requests.get(
            "https://api.coingecko.com/api/v3/simple/price",
            params={"ids": coin_id, "vs_currencies": "usd", "include_24hr_change": "true"},
            timeout=5
        )
        if r.status_code == 200:
            data = r.json().get(coin_id, {})
            change = abs(data.get("usd_24h_change", 0))
            if change < 2:
                level = "low"
            elif change < 5:
                level = "moderate"
            elif change < 10:
                level = "high"
            else:
                level = "extreme"
            return {
                "signal": "volatility",
                "level": level,
                "change_24h_pct": round(data.get("usd_24h_change", 0), 2),
                "ok": True
            }
    except Exception:
        pass
    return {"signal": "volatility", "level": "unknown", "change_24h": None, "ok": False}

# ── Verdict engine ────────────────────────────────────────────────────────────

def score_signal_for_action(sig: dict, action: str) -> tuple[bool, str]:
    """
    Return (aligned: bool, reason: str) — does this signal support the proposed action?
    """
    action = action.lower()

    name = sig.get("signal")

    if name == "sentiment":
        if not sig.get("ok"):
            return None, "sentiment unavailable"
        score = sig.get("score", 50)
        if action == "buy":
            aligned = score >= 55
            return aligned, f"sentiment={score}/100 ({'supports buy' if aligned else 'weak for buy'})"
        elif action == "sell":
            aligned = score <= 45
            return aligned, f"sentiment={score}/100 ({'supports sell' if aligned else 'weak for sell'})"
        else:  # hold
            aligned = 40 <= score <= 60
            return aligned, f"sentiment={score}/100 ({'neutral — supports hold' if aligned else 'directional — reconsider hold'})"

    elif name == "fear_greed":
        if not sig.get("ok"):
            return None, "fear/greed unavailable"
        score = sig.get("score", 50)
        fg_action = sig.get("action", "HOLD")
        if action == "buy":
            aligned = score <= 45 or fg_action in ("BUY", "ACCUMULATE")
            return aligned, f"fear_greed={score} ({fg_action}) {'→ good entry' if aligned else '→ overheated for buy'}"
        elif action == "sell":
            aligned = score >= 65 or fg_action in ("SELL", "REDUCE")
            return aligned, f"fear_greed={score} ({fg_action}) {'→ supports exit' if aligned else '→ too fearful for sell'}"
        else:
            aligned = fg_action == "HOLD"
            return aligned, f"fear_greed={score} ({fg_action}) {'→ hold confirmed' if aligned else '→ directional signal'}"

    elif name == "macro":
        if not sig.get("ok"):
            return None, "macro unavailable"
        env = sig.get("environment", "unknown")
        if action == "buy":
            aligned = env == "risk-on"
            return aligned, f"macro={env} ({'favorable for buy' if aligned else 'unfavorable — risk-off'})"
        elif action == "sell":
            aligned = env == "risk-off"
            return aligned, f"macro={env} ({'supports exit' if aligned else 'risk-on — consider staying'})"
        else:
            return True, f"macro={env} (neutral for hold)"

    elif name == "whale":
        if not sig.get("ok"):
            return None, "whale unavailable"
        verdict = sig.get("verdict", "neutral")
        if action == "buy":
            aligned = verdict == "accumulating"
            return aligned, f"whale={verdict} ({'smart money buying' if aligned else 'not accumulating'})"
        elif action == "sell":
            aligned = verdict == "distributing"
            return aligned, f"whale={verdict} ({'smart money selling' if aligned else 'not distributing'})"
        else:
            return True, f"whale={verdict} (neutral for hold)"

    elif name == "volatility":
        if not sig.get("ok"):
            return None, "volatility unavailable"
        level = sig.get("level", "unknown")
        if action == "buy":
            aligned = level in ("low", "moderate")
            return aligned, f"volatility={level} ({'safe entry' if aligned else 'high volatility — risky entry'})"
        elif action == "sell":
            aligned = level in ("low", "moderate")
            return aligned, f"volatility={level} ({'clean exit' if aligned else 'volatile — slippage risk'})"
        else:
            return True, f"volatility={level} (acceptable for hold)"

    return None, "unknown signal"


def compute_verdict(signals: list[dict], action: str) -> dict:
    """
    Evaluate all signals against the proposed action.
    Returns verdict, score, breakdown, and recommendation.
    """
    results = []
    aligned_count = 0
    available_count = 0

    for sig in signals:
        aligned, reason = score_signal_for_action(sig, action)
        if aligned is None:
            results.append({"signal": sig.get("signal"), "aligned": None, "reason": reason})
        else:
            available_count += 1
            if aligned:
                aligned_count += 1
            results.append({"signal": sig.get("signal"), "aligned": aligned, "reason": reason})

    # Score: aligned / available (ignore unavailable signals)
    score = round((aligned_count / available_count * 100) if available_count > 0 else 50)

    if available_count == 0:
        verdict = "WAIT"
        summary = "All signals unavailable — cannot evaluate. Try again in 60 seconds."
    elif aligned_count >= 4:
        verdict = "GO"
        summary = f"{aligned_count}/{available_count} signals align — high conviction {action.upper()}."
    elif aligned_count >= 2:
        verdict = "WAIT"
        summary = f"{aligned_count}/{available_count} signals align — mixed. Wait 15 minutes and re-check."
    else:
        verdict = "NO-GO"
        summary = f"{aligned_count}/{available_count} signals align — signals conflict with {action.upper()}. Do not proceed."

    # Confidence
    if available_count >= 4 and (aligned_count >= 4 or aligned_count <= 1):
        confidence = "high"
    elif available_count >= 3:
        confidence = "medium"
    else:
        confidence = "low"

    return {
        "verdict": verdict,
        "confidence": confidence,
        "alignment_score": score,
        "signals_evaluated": available_count,
        "signals_aligned": aligned_count,
        "summary": summary,
        "breakdown": results
    }

# ── Payment check ─────────────────────────────────────────────────────────────

def get_ip_hash(req) -> str:
    ip = req.headers.get("X-Forwarded-For", req.remote_addr or "unknown").split(",")[0].strip()
    return hashlib.sha256(ip.encode()).hexdigest()[:16]


def check_payment(req) -> tuple[bool, str]:
    """Returns (allowed, reason)."""
    if not PAYMENT_ENABLED:
        return True, "payment_disabled"
    ip_hash = get_ip_hash(req)
    calls = call_log.get(ip_hash, 0)
    if calls < FREE_CALLS_PER_IP:
        return True, f"free_tier ({calls + 1}/{FREE_CALLS_PER_IP})"
    payment_header = req.headers.get("X-Payment", "")
    if payment_header:
        return True, "paid"
    return False, "payment_required"

# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/v1/gate", methods=["GET"])
def execution_gate():
    """
    Main endpoint.
    GET /v1/gate?ticker=BTC&action=buy
    GET /v1/gate?ticker=PLTR&action=sell
    """
    global total_calls, total_paid_calls

    ticker = request.args.get("ticker", "").upper().strip()
    action = request.args.get("action", "").lower().strip()

    # Validate
    all_supported = SUPPORTED_CRYPTO + SUPPORTED_STOCKS
    if not ticker:
        return jsonify({"error": "ticker parameter required", "supported": all_supported}), 400
    if ticker not in all_supported:
        return jsonify({"error": f"ticker '{ticker}' not supported", "supported": all_supported}), 400
    if action not in SUPPORTED_ACTIONS:
        return jsonify({"error": f"action must be one of: {SUPPORTED_ACTIONS}"}), 400

    # Payment check
    allowed, pay_reason = check_payment(request)
    if not allowed:
        return jsonify({
            "error": "Payment required",
            "message": f"Free tier exhausted ({FREE_CALLS_PER_IP} calls/IP). Include X-Payment header with USDC on Base.",
            "call_cost_usd": CALL_COST_USD,
            "docs": "https://github.com/roblambert9/crypto-sentiment-starter"
        }), 402

    # Track
    ip_hash = get_ip_hash(request)
    call_log[ip_hash] = call_log.get(ip_hash, 0) + 1
    total_calls += 1
    if pay_reason == "paid":
        total_paid_calls += 1

    # Asset type
    asset_type = "crypto" if ticker in SUPPORTED_CRYPTO else "stock"

    # Fetch all 5 signals in parallel
    t_start = time.time()
    signals = []

    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {
            executor.submit(fetch_sentiment, ticker, asset_type): "sentiment",
            executor.submit(fetch_fear_greed, ticker): "fear_greed",
            executor.submit(fetch_macro): "macro",
            executor.submit(fetch_whale, ticker): "whale",
            executor.submit(compute_local_volatility, ticker): "volatility",
        }
        for future in as_completed(futures, timeout=8):
            try:
                signals.append(future.result())
            except Exception:
                pass

    elapsed = round(time.time() - t_start, 2)

    # Compute verdict
    verdict_data = compute_verdict(signals, action)

    return jsonify({
        "ticker": ticker,
        "action": action,
        "asset_type": asset_type,
        **verdict_data,
        "raw_signals": {s.get("signal"): s for s in signals if s.get("signal")},
        "call_cost_usd": CALL_COST_USD if pay_reason == "paid" else 0,
        "payment_status": pay_reason,
        "response_time_sec": elapsed,
        "timestamp": datetime.now(timezone.utc).isoformat()
    })


@app.route("/gate", methods=["GET"])
def gate_shortcut():
    """Convenience alias: /gate?ticker=BTC&action=buy"""
    return execution_gate()


@app.route("/health", methods=["GET"])
def health():
    uptime = round(time.time() - start_time)
    return jsonify({
        "status": "healthy",
        "agent": "16 — Execution Gate",
        "version": "1.0.0",
        "uptime_seconds": uptime,
        "payment_enabled": PAYMENT_ENABLED,
        "call_cost_usd": CALL_COST_USD,
        "free_calls_per_ip": FREE_CALLS_PER_IP,
        "supported_tickers": SUPPORTED_CRYPTO + SUPPORTED_STOCKS,
        "supported_actions": SUPPORTED_ACTIONS,
        "signal_sources": ["sentiment", "fear_greed", "macro", "whale", "volatility"],
        "timestamp": datetime.now(timezone.utc).isoformat()
    })


@app.route("/analytics", methods=["GET"])
def analytics():
    uptime = round(time.time() - start_time)
    return jsonify({
        "agent": "16 — Execution Gate",
        "total_calls": total_calls,
        "total_paid_calls": total_paid_calls,
        "free_calls": total_calls - total_paid_calls,
        "estimated_revenue_usd": round(total_paid_calls * CALL_COST_USD, 4),
        "unique_ips_seen": len(call_log),
        "uptime_seconds": uptime,
        "call_cost_usd": CALL_COST_USD,
        "timestamp": datetime.now(timezone.utc).isoformat()
    })


@app.route("/", methods=["GET"])
def index():
    return jsonify({
        "name": "Execution Gate API — Agent 16",
        "description": "Pre-trade guardrail for AI agents. Aggregates 5 signals into GO / NO-GO / WAIT verdict.",
        "endpoints": {
            "GET /v1/gate?ticker=BTC&action=buy": "Main gate check — returns verdict",
            "GET /gate?ticker=BTC&action=buy": "Alias for /v1/gate",
            "GET /health": "Service health + config",
            "GET /analytics": "Call count + revenue"
        },
        "example": "curl 'https://your-railway-url.up.railway.app/v1/gate?ticker=BTC&action=buy'",
        "price": f"${CALL_COST_USD}/call (USDC on Base via x402)",
        "free_tier": f"{FREE_CALLS_PER_IP} calls/IP",
        "docs": "https://github.com/roblambert9/crypto-sentiment-starter"
    })


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
