# Composio Tool Submission — Execution Gate API

## Tool Name
execution_gate

## Tool Description (for Composio registry)
Pre-trade safety check for AI trading agents. Aggregates 5 live market signals (sentiment, fear/greed, macro, whale activity, volatility) and returns a single GO / NO-GO / WAIT verdict before any buy or sell is executed. Call this tool before any trade action to prevent the agent from acting against market conditions.

## Tool Schema

```json
{
  "name": "execution_gate",
  "description": "Pre-trade guardrail. Aggregates 5 live signals and returns GO/NO-GO/WAIT before executing a buy or sell. Always call this before any trade action. Respect NO-GO verdicts.",
  "parameters": {
    "type": "object",
    "properties": {
      "ticker": {
        "type": "string",
        "description": "Asset symbol to check. Crypto: BTC, ETH, SOL, BNB, XRP, DOGE, ADA, AVAX, MATIC, LINK. Stocks: PLTR, TSLA, NVDA, ORCL, MSFT, GOOG, META, AMZN, AAPL, COIN, IREN. Always uppercase."
      },
      "action": {
        "type": "string",
        "enum": ["buy", "sell", "hold"],
        "description": "The trade action you intend to take. The gate evaluates all signals against this action."
      }
    },
    "required": ["ticker", "action"]
  }
}
```

## Python Implementation for Composio

```python
import requests
from composio import ComposioToolSet, Action

GATE_URL = "https://execution-gate-api-production.up.railway.app"

def execution_gate(ticker: str, action: str) -> dict:
    """
    Pre-trade safety check.
    Returns verdict (GO/NO-GO/WAIT), confidence, and signal breakdown.
    """
    r = requests.get(
        f"{GATE_URL}/v1/gate",
        params={"ticker": ticker.upper(), "action": action.lower()},
        timeout=15
    )

    if r.status_code == 402:
        return {"error": "Payment required", "verdict": "WAIT", "message": "Free tier exhausted"}

    d = r.json()

    # Return clean summary for agent consumption
    return {
        "verdict": d.get("verdict", "WAIT"),
        "confidence": d.get("confidence", "low"),
        "summary": d.get("summary", ""),
        "proceed": d.get("verdict") == "GO",
        "signals_aligned": d.get("signals_aligned", 0),
        "signals_evaluated": d.get("signals_evaluated", 0),
        "breakdown": [
            f"{'✓' if b.get('aligned') else '✗'} {b['signal']}: {b['reason']}"
            for b in d.get("breakdown", [])
        ]
    }
```

## Use Case Examples

### LangChain Agent Workflow
```python
# Agent checks gate before executing
gate_result = execution_gate("BTC", "buy")

if gate_result["proceed"]:
    # Gate cleared — execute the trade
    execute_buy("BTC", amount=0.01)
elif gate_result["verdict"] == "WAIT":
    # Schedule retry
    schedule_retry(minutes=15)
else:
    # NO-GO — log and abort
    log_blocked_trade("BTC", "buy", gate_result["summary"])
```

### CrewAI Pre-Trade Task
```python
from crewai import Task

gate_check_task = Task(
    description="Before executing any trade, use the execution_gate tool to check if conditions support the action. If verdict is NO-GO, abort and report why.",
    agent=risk_manager_agent,
    expected_output="GO/NO-GO/WAIT verdict with signal breakdown"
)
```

### AutoGPT Command
```
COMMAND: execution_gate
ARGS: {"ticker": "ETH", "action": "buy"}
RESULT: {"verdict": "GO", "confidence": "high", "proceed": true, ...}
```

## Why This Tool Belongs in Composio

1. **Prevents costly mistakes.** AI agents acting on a single signal can fire at the worst possible time. The gate requires multi-signal consensus.

2. **Agent-native output.** Verdict is `GO`/`NO-GO`/`WAIT` — unambiguous strings the agent can branch on without parsing.

3. **Composable with other tools.** Designed to sit between "decide to trade" and "execute trade" in any tool chain.

4. **Live data.** Pulls from 5 real-time signal sources in parallel. Not a static rule set.

5. **Free to test.** 20 free calls/IP. Agents can integrate and validate before paying anything.

## API Details

- **Endpoint:** `GET /v1/gate?ticker=BTC&action=buy`
- **Hosting:** Railway (production, auto-restart)
- **Response time:** ~800ms–1200ms (5 parallel signal fetches)
- **Price:** $0.010 USDC/call (x402 on Base) after free tier
- **Docs:** https://github.com/roblambert9/crypto-sentiment-starter

## Contact
Robert Lambert — roblambert9@gmail.com
