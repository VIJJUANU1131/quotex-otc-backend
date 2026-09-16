import json
import asyncio
import websockets

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Deriv Live Market API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DERIV_WS = "wss://api.derivws.com/trading/v1/options/ws/public"


async def deriv_request(request):
    async with websockets.connect(
        DERIV_WS,
        ping_interval=20,
        ping_timeout=20
    ) as ws:

        await ws.send(json.dumps(request))

        while True:
            message = await ws.recv()
            data = json.loads(message)

            if data.get("req_id") == request.get("req_id"):
                return data

            if data.get("msg_type") in ["error"]:
                return data


@app.get("/")
async def root():
    return {
        "status": "online",
        "market": "DERIV_SYNTHETIC",
        "timeframe": "M1"
    }


@app.get("/api/v1/candles")
async def candles(
    symbol: str = Query("1HZ100V"),
    count: int = Query(100, ge=10, le=500)
):

    request = {
        "ticks_history": symbol,
        "count": count,
        "end": "latest",
        "style": "candles",
        "granularity": 60,
        "req_id": 1001
    }

    data = await deriv_request(request)

    if data.get("msg_type") == "error":
        return {
            "status": "error",
            "market": "DERIV_SYNTHETIC",
            "symbol": symbol,
            "error": data.get("error")
        }

    candles_data = data.get("candles", [])

    return {
        "status": "success",
        "market": "DERIV_SYNTHETIC",
        "symbol": symbol,
        "timeframe": "M1",
        "count": len(candles_data),
        "candles": candles_data
    }


@app.get("/api/v1/tick")
async def tick(symbol: str = Query("1HZ100V")):

    request = {
        "ticks_history": symbol,
        "count": 1,
        "end": "latest",
        "style": "ticks",
        "req_id": 2001
    }

    data = await deriv_request(request)

    if data.get("msg_type") == "error":
        return {
            "status": "error",
            "symbol": symbol,
            "error": data.get("error")
        }

    history = data.get("history", {})

    prices = history.get("prices", [])
    times = history.get("times", [])

    if not prices:
        return {
            "status": "error",
            "message": "No price received"
        }

    return {
        "status": "success",
        "market": "DERIV_SYNTHETIC",
        "symbol": symbol,
        "price": prices[-1],
        "epoch": times[-1] if times else None
    }
