import os
import asyncio
import time
from typing import Dict, List

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from pyquotex.stable_api import Quotex


app = FastAPI(title="Quotex Real Market Data API")


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


QUOTEX_EMAIL = os.getenv("QUOTEX_EMAIL")
QUOTEX_PASSWORD = os.getenv("QUOTEX_PASSWORD")


# Common Quotex symbols.
# OTC symbols are included only as symbol names; availability
# depends on the connected Quotex account/session.
PAIRS = [
    "EURUSD",
    "GBPUSD",
    "USDJPY",
    "AUDUSD",
    "USDCAD",
    "USDCHF",
    "NZDUSD",
    "EURGBP",
    "EURJPY",
    "GBPJPY",
    "AUDJPY",
    "EURAUD",
    "GBPAUD",
    "GBPCAD",
    "AUDCAD",
    "AUDNZD",
    "NZDJPY",
    "CADJPY",
    "CHFJPY",
]


client = None
client_lock = asyncio.Lock()


async def get_client():
    global client

    async with client_lock:

        if client is not None:
            try:
                if await client.check_connect():
                    return client
            except Exception:
                pass

        if not QUOTEX_EMAIL or not QUOTEX_PASSWORD:
            raise RuntimeError(
                "QUOTEX_EMAIL / QUOTEX_PASSWORD not configured"
            )

        client = Quotex(
            email=QUOTEX_EMAIL,
            password=QUOTEX_PASSWORD,
            lang="en",
            asset_default="EURUSD",
            period_default=60,
        )

        connected, reason = await client.connect()

        if not connected:
            client = None
            raise RuntimeError(
                f"Quotex connection failed: {reason}"
            )

        return client


def normalize_candles(raw_candles) -> List[dict]:
    result = []

    if not raw_candles:
        return result

    if isinstance(raw_candles, dict):

        items = raw_candles.items()

    elif isinstance(raw_candles, list):

        items = enumerate(raw_candles)

    else:
        return result

    for timestamp, candle in items:

        if not isinstance(candle, dict):
            continue

        try:
            epoch = int(float(timestamp))
        except Exception:
            epoch = int(time.time())

        try:
            open_price = float(
                candle.get("open", candle.get("Open", 0))
            )

            high_price = float(
                candle.get("high", candle.get("High", 0))
            )

            low_price = float(
                candle.get("low", candle.get("Low", 0))
            )

            close_price = float(
                candle.get("close", candle.get("Close", 0))
            )

        except Exception:
            continue

        if open_price == 0 and close_price == 0:
            continue

        result.append(
            {
                "epoch": epoch,
                "open": open_price,
                "high": high_price,
                "low": low_price,
                "close": close_price,
            }
        )

    result.sort(key=lambda x: x["epoch"])

    return result


async def get_real_candles(
    symbol: str,
    period: int = 60,
):
    q = await get_client()

    # Start real-time candle stream.
    await q.start_candles_stream(
        symbol,
        period
    )

    # Give the stream a moment to populate.
    await asyncio.sleep(1)

    raw = await q.get_realtime_candles(
        symbol,
        period
    )

    candles = normalize_candles(raw)

    return candles


@app.get("/")
async def root():

    return {
        "status": "online",
        "market": "QUOTEX",
        "data": "REAL",
        "timeframe": "M1",
        "pairs": len(PAIRS),
        "source": "Unofficial PyQuotex WebSocket",
    }


@app.get("/api/v1/pairs")
async def available_pairs():

    return {
        "status": "success",
        "market": "QUOTEX",
        "pairs": PAIRS,
    }


@app.get("/api/v1/candles")
async def candles(
    symbol: str = Query(
        "EURUSD",
        description="Quotex symbol"
    ),
    timeframe: str = Query(
        "M1",
        description="M1 or M5"
    ),
):

    symbol = symbol.strip()

    timeframe = timeframe.upper()

    if timeframe == "M1":
        period = 60

    elif timeframe == "M5":
        period = 300

    else:
        return {
            "status": "error",
            "message": "Supported timeframes: M1, M5"
        }

    try:

        candles_data = await get_real_candles(
            symbol,
            period
        )

        if not candles_data:

            return {
                "status": "error",
                "market": "QUOTEX",
                "data": "REAL",
                "symbol": symbol,
                "timeframe": timeframe,
                "message": "No real candles received"
            }

        return {
            "status": "success",
            "market": "QUOTEX",
            "data": "REAL",
            "symbol": symbol,
            "timeframe": timeframe,
            "candles": candles_data[-100:]
        }

    except Exception as e:

        return {
            "status": "error",
            "market": "QUOTEX",
            "data": "REAL",
            "symbol": symbol,
            "timeframe": timeframe,
            "message": str(e)
        }


@app.get("/api/v1/all-candles")
async def all_candles(
    timeframe: str = Query("M1")
):

    timeframe = timeframe.upper()

    if timeframe == "M1":
        period = 60

    elif timeframe == "M5":
        period = 300

    else:
        return {
            "status": "error",
            "message": "Supported timeframes: M1, M5"
        }

    output = {}

    for symbol in PAIRS:

        try:

            candles_data = await get_real_candles(
                symbol,
                period
            )

            if candles_data:

                output[symbol] = {
                    "status": "success",
                    "candles": candles_data[-100:]
                }

            else:

                output[symbol] = {
                    "status": "error",
                    "message": "No candles"
                }

        except Exception as e:

            output[symbol] = {
                "status": "error",
                "message": str(e)
            }

    return {
        "status": "success",
        "market": "QUOTEX",
        "data": "REAL",
        "timeframe": timeframe,
        "pairs": output
    }


@app.on_event("shutdown")
async def shutdown():

    global client

    if client is not None:

        try:
            await client.close()
        except Exception:
            pass

        client = None
