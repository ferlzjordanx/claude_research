"""A fake FX rate service for local demos (port 9000).

    FAKE_FX_DELAY=5 uvicorn scripts.fake_fx:app --port 9000

Set FAKE_FX_DELAY to make it slow and watch timeouts become 504s.
"""

import asyncio
import os

from fastapi import FastAPI, Request

app = FastAPI(title="Fake FX")
RATES = {"EUR": 0.92, "GBP": 0.79, "JPY": 149.5}


@app.get("/rates")
async def rates(request: Request, symbol: str = "EUR") -> dict[str, float]:
    await asyncio.sleep(float(os.getenv("FAKE_FX_DELAY", "0")))
    # The caller's trace continues here if we were instrumented too.
    print("traceparent:", request.headers.get("traceparent"))
    return {"rate": RATES.get(symbol, 1.0)}
