# RapidAPI Listing — Execution Gate API

## Title
Execution Gate API — Pre-Trade Safety Check for AI Agents

## Short Description (160 chars)
One endpoint before any buy or sell. Aggregates 5 live signals and returns GO / NO-GO / WAIT. Built for AI trading agents and LangChain tools.

## Full Description

The Execution Gate is a pre-trade guardrail designed to be the last call before any AI agent executes a buy or sell.

Instead of letting your agent act on a single signal, the Execution Gate queries five independent sources simultaneously and evaluates whether they collectively support your intended action. One decisive verdict — GO, NO-GO, or WAIT — with full signal breakdown.

**5 signals evaluated per call:**
- News sentiment score (from live headline analysis)
- Composite Fear & Greed index (sentiment + social + volatility weighted)
- Macro environment (Fed stance, oil pressure, risk-on vs risk-off)
- Whale wallet behavior (accumulation vs distribution pressure)
- Local volatility classification (24h price change)

**Verdict logic:**
- **GO** — 4+ signals align. High conviction. Proceed.
- **WAIT** — 2–3 signals align. Mixed market. Retry in 15 minutes.
- **NO-GO** — 0–1 signals align. Signals conflict with action. Abort.

**Works for both crypto and stocks:**
Crypto: BTC, ETH, SOL, BNB, XRP, DOGE, ADA, AVAX, MATIC, LINK
Stocks: PLTR, TSLA, NVDA, ORCL, MSFT, GOOG, META, AMZN, AAPL, COIN, IREN

**Built for AI agents.** Consistent JSON schema. Machine-readable verdicts. LangChain Tool wrapper included in docs. Compatible with CrewAI, AutoGPT, and any agentic workflow.

**Response includes:** verdict, confidence, alignment_score, signals_evaluated, signals_aligned, summary, full breakdown with per-signal reasoning.

## Category
Finance / AI Tools / Crypto / Algorithmic Trading

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | /v1/gate | Main gate check — returns verdict |
| GET | /gate | Alias for /v1/gate |
| GET | /health | Service health + supported tickers |
| GET | /analytics | Usage stats |

## Parameters

| Name | Required | Type | Description |
|------|----------|------|-------------|
| ticker | Yes | string | Asset symbol: BTC, ETH, PLTR, etc. |
| action | Yes | string | buy, sell, or hold |

## Pricing Tiers

| Tier | Price | Calls |
|------|-------|-------|
| Free | $0 | 20 calls/IP |
| Basic | $9.99/month | 2,000 calls |
| Pro | $29.99/month | 10,000 calls |
| Ultra | $0.010/call | Pay as you go |

## Curl Examples

```bash
# BTC buy check
curl "https://execution-gate-api-production.up.railway.app/v1/gate?ticker=BTC&action=buy"

# PLTR sell check
curl "https://execution-gate-api-production.up.railway.app/v1/gate?ticker=PLTR&action=sell"

# ETH hold check
curl "https://execution-gate-api-production.up.railway.app/v1/gate?ticker=ETH&action=hold"

# Health check
curl "https://execution-gate-api-production.up.railway.app/health"
```

## Sample Response (GO verdict)

```json
{
  "ticker": "BTC",
  "action": "buy",
  "verdict": "GO",
  "confidence": "high",
  "alignment_score": 85,
  "signals_evaluated": 5,
  "signals_aligned": 4,
  "summary": "4/5 signals align — high conviction BUY.",
  "breakdown": [
    {"signal": "sentiment",  "aligned": true,  "reason": "sentiment=71/100 (supports buy)"},
    {"signal": "fear_greed", "aligned": true,  "reason": "fear_greed=38 (ACCUMULATE) → good entry"},
    {"signal": "macro",      "aligned": true,  "reason": "macro=risk-on (favorable for buy)"},
    {"signal": "whale",      "aligned": true,  "reason": "whale=accumulating (smart money buying)"},
    {"signal": "volatility", "aligned": false, "reason": "volatility=high (risky entry)"}
  ],
  "call_cost_usd": 0.01,
  "response_time_sec": 0.94,
  "timestamp": "2026-03-30T14:00:00Z"
}
```

## Sample Response (NO-GO verdict)

```json
{
  "ticker": "BTC",
  "action": "buy",
  "verdict": "NO-GO",
  "confidence": "high",
  "alignment_score": 20,
  "signals_evaluated": 5,
  "signals_aligned": 1,
  "summary": "1/5 signals align — signals conflict with BUY. Do not proceed.",
  "breakdown": [
    {"signal": "sentiment",  "aligned": false, "reason": "sentiment=28/100 (weak for buy)"},
    {"signal": "fear_greed", "aligned": false, "reason": "fear_greed=82 (SELL) → overheated for buy"},
    {"signal": "macro",      "aligned": false, "reason": "macro=risk-off (unfavorable — risk-off)"},
    {"signal": "whale",      "aligned": false, "reason": "whale=distributing (not accumulating)"},
    {"signal": "volatility", "aligned": true,  "reason": "volatility=low (safe entry)"}
  ]
}
```

## Tags
execution gate, pre-trade, trading safety, AI agents, LangChain, crypto, BTC, ETH, signal aggregation, algo trading, guardrail

## Website / Documentation
https://github.com/roblambert9/crypto-sentiment-starter
