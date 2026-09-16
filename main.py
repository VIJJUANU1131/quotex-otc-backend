import json
import asyncio
import websockets

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DERIV_WS = "wss://api.derivws.com/trading/v1/options/ws/public"


async def get_candles(symbol="1HZ100V"):
    request = {
        "ticks_history": symbol,
        "count": 100,
        "end": "latest",
        "style": "candles",
        "granularity": 60,
        "req_id": 1
    }

    async with websockets.connect(DERIV_WS) as ws:
        await ws.send(json.dumps(request))

        while True:
            message = await ws.recv()
            data = json.loads(message)

            if data.get("req_id") == 1:
                return data


@app.get("/")
async def home():
    return {
        "status": "online",
        "market": "DERIV_SYNTHETIC",
        "timeframe": "M1"
    }


@app.get("/api/v1/candles")
async def candles():
    try:
        data = await get_candles("1HZ100V")

        if data.get("error"):
            return {
                "status": "error",
                "error": data["error"]
            }

        return {
            "status": "success",
            "market": "DERIV_SYNTHETIC",
            "symbol": "1HZ100V",
            "timeframe": "M1",
            "candles": data.get("candles", [])
        }

    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }
