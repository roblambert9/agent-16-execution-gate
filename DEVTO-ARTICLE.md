# Dev.to Article — Execution Gate API

**Title:** How to add a pre-trade safety gate to your AI trading agent (with LangChain example)

**Tags:** python, langchain, aiagents, crypto, trading

---

If you're building an AI trading agent, you've probably run into this: the agent fires a buy on one signal, the signal turns out to be noise, and you lose money on a position you never should have taken.

The fix is a pre-trade gate — a check that runs before any order executes and requires multiple independent signals to agree before giving the green light.

Here's how I built one and how to add it to any Python trading agent in about 10 minutes.

---

## The Problem With Single-Signal Agents

Most AI trading agents are built something like this:

```python
sentiment = get_sentiment("BTC")
if sentiment["score"] > 65:
    execute_buy("BTC", amount=0.1)
```

The problem: sentiment alone is noisy. A single bullish headline can push a score above your threshold even when the macro environment is risk-off, whale wallets are distributing, and the Fear & Greed index is screaming extreme greed.

You want to know that multiple independent signals agree before committing capital.

---

## The Execution Gate Pattern

The gate works by querying 5 independent signal sources in parallel and scoring them against your intended action:

| Signal | Source | What it checks |
|--------|--------|----------------|
| Sentiment | News headline analysis | Bullish/bearish language around ticker |
| Fear & Greed | Composite index | Market emotion (0–100) |
| Macro | Fed/oil/CPI | Risk-on vs risk-off environment |
| Whale activity | Exchange flows | Large wallet accumulation vs distribution |
| Volatility | Price data | 24h price change magnitude |

**Verdict:**
- `GO` — 4+ signals align → proceed
- `WAIT` — 2–3 align → mixed, retry in 15 min
- `NO-GO` — 0–1 align → abort

---

## The API

I've built this as a live REST API you can call directly:

```bash
curl "https://execution-gate-api-production.up.railway.app/v1/gate?ticker=BTC&action=buy"
```

Response:

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
  "response_time_sec": 0.94
}
```

Free tier: 20 calls/IP. No key required. Paid tier: $0.01/call USDC on Base.

---

## Adding the Gate to a Python Agent

Here's a minimal wrapper you can drop into any script:

```python
import requests

GATE_URL = "https://execution-gate-api-production.up.railway.app"

def check_gate(ticker: str, action: str) -> dict:
    """Returns gate verdict before executing a trade."""
    r = requests.get(
        f"{GATE_URL}/v1/gate",
        params={"ticker": ticker.upper(), "action": action.lower()},
        timeout=15
    )
    return r.json()

def safe_buy(ticker: str, amount: float):
    gate = check_gate(ticker, "buy")

    if gate["verdict"] == "GO":
        print(f"Gate cleared ({gate['confidence']} confidence) — executing buy")
        print(f"  {gate['summary']}")
        # execute_buy(ticker, amount)  ← your execution logic here
    elif gate["verdict"] == "WAIT":
        print(f"Gate says wait: {gate['summary']}")
        # schedule a retry in 15 min
    else:
        print(f"Gate blocked: {gate['summary']}")
        for b in gate["breakdown"]:
            status = "✓" if b.get("aligned") else "✗"
            print(f"  {status} {b['signal']}: {b['reason']}")

# Usage
safe_buy("BTC", 0.01)
```

---

## LangChain Tool Wrapper

For LangChain agents, wrap it as a `Tool`:

```python
from langchain.tools import Tool
import requests

def execution_gate_check(query: str) -> str:
    """
    Input: "ticker=BTC action=buy"
    """
    parts = dict(p.split("=") for p in query.strip().split())
    ticker = parts.get("ticker", "BTC").upper()
    action = parts.get("action", "buy").lower()

    r = requests.get(
        "https://execution-gate-api-production.up.railway.app/v1/gate",
        params={"ticker": ticker, "action": action},
        timeout=15
    )
    d = r.json()

    result = f"Verdict: {d['verdict']} | Confidence: {d['confidence']}\n{d['summary']}"
    for b in d.get("breakdown", []):
        status = "✓" if b.get("aligned") else "✗"
        result += f"\n  {status} {b['signal']}: {b['reason']}"
    return result

gate_tool = Tool(
    name="execution_gate",
    description=(
        "Pre-trade safety check — call this BEFORE any buy or sell. "
        "Input format: 'ticker=BTC action=buy'. "
        "Returns GO (proceed), NO-GO (abort), or WAIT (retry in 15 min). "
        "Always follow a NO-GO verdict."
    ),
    func=execution_gate_check
)
```

Now add `gate_tool` to your agent's tools list. The agent will call the gate before any trade decision.

---

## The Verdict Logic in Plain English

For a **BUY** to get GO:
- Sentiment score > 55 (more bullish than bearish headlines)
- Fear & Greed < 45 OR signal is ACCUMULATE/BUY (not overbought)
- Macro is risk-on (Fed not hiking aggressively, oil stable)
- Whale wallets are accumulating (coins leaving exchanges)
- Volatility is low or moderate (not a 10%+ swing day)

For a **SELL** to get GO:
- Sentiment < 45 (bearish headlines dominating)
- Fear & Greed > 65 OR signal is SELL/REDUCE (market is greedy — good exit)
- Macro is risk-off
- Whale wallets are distributing (coins entering exchanges)
- Volatility is low/moderate (clean exit)

4 out of 5 of these need to be true. If only 2–3 are true, you wait. If fewer than 2, you abort.

---

## Supported Tickers

**Crypto:** BTC, ETH, SOL, BNB, XRP, DOGE, ADA, AVAX, MATIC, LINK  
**Stocks:** PLTR, TSLA, NVDA, ORCL, MSFT, GOOG, META, AMZN, AAPL, COIN, IREN

---

## Run Your Own Instance

The source is open. Deploy in 5 minutes:

```bash
git clone https://github.com/roblambert9/crypto-sentiment-starter
cd agent-16-execution-gate
railway up
```

Configure the upstream agent URLs as env vars if you're pointing at your own signal sources.

---

## Closing Thought

A gate doesn't prevent you from trading. It prevents you from trading at the wrong time.

The agents that get rich aren't the ones with the best entry signals — they're the ones that don't blow up when the signals are wrong.

Full source, all 16 agents, LangChain examples:  
**github.com/roblambert9/crypto-sentiment-starter**
