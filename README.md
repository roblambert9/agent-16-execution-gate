# Execution Gate API — Agent 16

**Pre-trade guardrail for AI agents.**  
One call before any buy or sell. Returns GO / NO-GO / WAIT.

```bash
curl "https://your-url.up.railway.app/v1/gate?ticker=BTC&action=buy"
```

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
    {"signal": "sentiment",   "aligned": true,  "reason": "sentiment=71/100 (supports buy)"},
    {"signal": "fear_greed",  "aligned": true,  "reason": "fear_greed=38 (ACCUMULATE) → good entry"},
    {"signal": "macro",       "aligned": true,  "reason": "macro=risk-on (favorable for buy)"},
    {"signal": "whale",       "aligned": true,  "reason": "whale=accumulating (smart money buying)"},
    {"signal": "volatility",  "aligned": false, "reason": "volatility=high (risky entry)"}
  ]
}
```

---

## What It Does

Before your AI agent executes a trade, it calls the Execution Gate. The gate queries 5 independent signal sources in parallel and evaluates whether they support your intended action:

| Signal | Source | What it checks |
|--------|--------|----------------|
| Sentiment | Agent 4a/4b | News sentiment score for the ticker |
| Fear & Greed | Agent 4i | Composite market emotion (0–100) |
| Macro | Agent 4d | Fed stance, oil pressure, risk-on/off |
| Whale | Agent 4e | Large wallet accumulation vs distribution |
| Volatility | CoinGecko | 24h price change as volatility proxy |

**Verdict logic:**
- `GO` — 4+ of 5 signals align with your action
- `WAIT` — 2–3 signals align — mixed, try again in 15 min
- `NO-GO` — 0–1 signals align — do not proceed

---

## Endpoints

### `GET /v1/gate`
Main gate check.

**Parameters:**
| Param | Required | Values |
|-------|----------|--------|
| `ticker` | yes | BTC, ETH, SOL, PLTR, TSLA, NVDA, ORCL, + more |
| `action` | yes | `buy`, `sell`, `hold` |

**Supported tickers:**
- Crypto: BTC, ETH, SOL, BNB, XRP, DOGE, ADA, AVAX, MATIC, LINK
- Stocks: PLTR, TSLA, NVDA, ORCL, MSFT, GOOG, META, AMZN, AAPL, COIN, IREN

### `GET /gate`
Alias for `/v1/gate` — same parameters.

### `GET /health`
Service health, config, supported tickers.

### `GET /analytics`
Call count, revenue, unique IPs.

---

## Pricing

| Tier | Price |
|------|-------|
| Free | 20 calls/IP |
| Paid | $0.010 USDC/call via [x402](https://x402.org) on Base |

Include `X-Payment` header for paid calls.

---

## Quickstart

```bash
# Install
pip install requests

# Test free tier
curl "https://your-url.up.railway.app/v1/gate?ticker=BTC&action=buy"
curl "https://your-url.up.railway.app/v1/gate?ticker=PLTR&action=sell"
curl "https://your-url.up.railway.app/v1/gate?ticker=ETH&action=hold"
```

```python
import requests

def check_gate(ticker: str, action: str, api_url: str) -> dict:
    r = requests.get(
        f"{api_url}/v1/gate",
        params={"ticker": ticker, "action": action},
        timeout=15
    )
    return r.json()

# Check before executing a buy
result = check_gate("BTC", "buy", "https://your-url.up.railway.app")

if result["verdict"] == "GO":
    print(f"Gate cleared — {result['summary']}")
    # execute_trade(...)
elif result["verdict"] == "WAIT":
    print(f"Hold off — {result['summary']}")
else:
    print(f"Blocked — {result['summary']}")
```

```javascript
async function checkGate(ticker, action, apiUrl) {
  const res = await fetch(`${apiUrl}/v1/gate?ticker=${ticker}&action=${action}`);
  return res.json();
}

const gate = await checkGate("BTC", "buy", "https://your-url.up.railway.app");
if (gate.verdict === "GO") {
  console.log("Gate cleared:", gate.summary);
} else {
  console.log(`Gate blocked (${gate.verdict}):`, gate.summary);
}
```

---

## LangChain Integration

```python
from langchain.tools import Tool
import requests

def execution_gate_check(query: str) -> str:
    """
    Query format: "ticker=BTC action=buy"
    Returns GO/NO-GO/WAIT with reasoning.
    """
    parts = dict(p.split("=") for p in query.split())
    ticker = parts.get("ticker", "BTC").upper()
    action = parts.get("action", "buy").lower()

    r = requests.get(
        "https://your-url.up.railway.app/v1/gate",
        params={"ticker": ticker, "action": action},
        timeout=15
    )
    d = r.json()
    verdict = d.get("verdict", "WAIT")
    confidence = d.get("confidence", "low")
    summary = d.get("summary", "")
    breakdown = d.get("breakdown", [])

    result = f"Execution Gate: {verdict} (confidence: {confidence})\n{summary}"
    for b in breakdown:
        status = "✓" if b.get("aligned") else "✗"
        result += f"\n  {status} {b['signal']}: {b['reason']}"
    return result

gate_tool = Tool(
    name="execution_gate",
    description=(
        "Pre-trade safety check. Call this BEFORE executing any buy or sell. "
        "Input format: 'ticker=BTC action=buy'. "
        "Returns GO (proceed), NO-GO (abort), or WAIT (retry in 15 min). "
        "Always respect a NO-GO verdict."
    ),
    func=execution_gate_check
)
```

---

## Deploy to Railway

```bash
# Clone
git clone https://github.com/roblambert9/crypto-sentiment-starter
cd agent-16-execution-gate

# Deploy
railway login
railway init
railway up
```

**Optional env vars:**
```
CALL_COST_USD=0.010
FREE_CALLS_PER_IP=20
PAYMENT_ENABLED=false
SENTIMENT_URL=https://crypto-sentiment-api-production.up.railway.app
FEAR_GREED_URL=https://fear-greed-api-production.up.railway.app
MACRO_URL=https://macro-signal-api-production.up.railway.app
WHALE_URL=https://whale-monitor-api-production.up.railway.app
```

---

## Part of the Agent Army

This is Agent 16 in a fleet of 16 specialized trading intelligence APIs. Each agent handles one signal type. The Execution Gate is the final layer — it calls 5 agents and decides whether to let a trade through.

Full army: [github.com/roblambert9/crypto-sentiment-starter](https://github.com/roblambert9/crypto-sentiment-starter)

---

*Built in Ottawa. Deploying to Yucatán, Mexico by 2030.*
