import os
import asyncio
import time
import logging
from typing import List

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from pyquotex.stable_api import Quotex


# =========================================================
# LOGGING
# =========================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

logger = logging.getLogger("quotex-backend")


# =========================================================
# FASTAPI
# =========================================================

app = FastAPI(
    title="Quotex Real Market Data API",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =========================================================
# ENVIRONMENT VARIABLES
# =========================================================

QUOTEX_EMAIL = os.getenv("QUOTEX_EMAIL")
QUOTEX_PASSWORD = os.getenv("QUOTEX_PASSWORD")


# =========================================================
# PAIRS
# =========================================================

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


# =========================================================
# GLOBAL CLIENT
# =========================================================

client = None
client_lock = asyncio.Lock()


# =========================================================
# QUOTEX CLIENT
# =========================================================

async def get_client():

    global client

    async with client_lock:

        # Already connected?
        if client is not None:

            try:

                connected = await client.check_connect()

                if connected:
                    return client

            except Exception as e:

                logger.warning(
                    "Existing connection check failed: %s",
                    str(e)
                )

        # Credentials check
        if not QUOTEX_EMAIL:
            raise RuntimeError(
                "QUOTEX_EMAIL is not configured in Render Environment Variables"
            )

        if not QUOTEX_PASSWORD:
            raise RuntimeError(
                "QUOTEX_PASSWORD is not configured in Render Environment Variables"
            )

        logger.info("Creating Quotex client...")

        # Create client
        client = Quotex(
            email=QUOTEX_EMAIL,
            password=QUOTEX_PASSWORD,
            host="qxbroker.com",
            lang="en",
            asset_default="EURUSD",
            period_default=60,
        )

        # Enable PyQuotex websocket debug logging
        client.debug_ws_enable = True

        logger.info("Connecting to Quotex...")

        try:

            connected, reason = await client.connect()

        except Exception as e:

            client = None

            logger.exception(
                "Quotex connection exception"
            )

            raise RuntimeError(
                f"Quotex connection exception: {str(e)}"
            )

        if not connected:

            client = None

            raise RuntimeError(
                f"Quotex connection failed: {reason}"
            )

        logger.info(
            "Quotex connection successful: %s",
            reason
        )

        return client


# =========================================================
# NORMALIZE CANDLES
# =========================================================

def normalize_candles(raw_candles) -> List[dict]:

    result = []

    if not raw_candles:
        return result

    # Dictionary format
    if isinstance(raw_candles, dict):

        items = raw_candles.items()

    # List format
    elif isinstance(raw_candles, list):

        items = enumerate(raw_candles)

    else:

        return result

    for timestamp, candle in items:

        if not isinstance(candle, dict):
            continue

        # Timestamp
        try:

            epoch = int(float(timestamp))

        except Exception:

            epoch = int(time.time())

        try:

            open_price = float(
                candle.get(
                    "open",
                    candle.get(
                        "Open",
                        0
                    )
                )
            )

            high_price = float(
                candle.get(
                    "high",
                    candle.get(
                        "High",
                        0
                    )
                )
            )

            low_price = float(
                candle.get(
                    "low",
                    candle.get(
                        "Low",
                        0
                    )
                )
            )

            close_price = float(
                candle.get(
                    "close",
                    candle.get(
                        "Close",
                        0
                    )
                )
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

    result.sort(
        key=lambda x: x["epoch"]
    )

    return result


# =========================================================
# GET REAL CANDLES
# =========================================================

async def get_real_candles(
    symbol: str,
    period: int = 60
):

    q = await get_client()

    logger.info(
        "Starting candle stream: %s | %s seconds",
        symbol,
        period
    )

    await q.start_candles_stream(
        symbol,
        period
    )

    # Give websocket a moment
    await asyncio.sleep(2)

    raw = await q.get_realtime_candles(
        symbol,
        period
    )

    candles = normalize_candles(
        raw
    )

    logger.info(
        "Received %s candles for %s",
        len(candles),
        symbol
    )

    return candles


# =========================================================
# ROOT
# =========================================================

@app.get("/")
async def root():

    return {
        "status": "online",
        "market": "QUOTEX",
        "data": "REAL",
        "timeframe": "M1",
        "pairs": len(PAIRS),
        "source": "Unofficial PyQuotex WebSocket",
        "python": "3.12+",
        "debug": True
    }


# =========================================================
# CREDENTIAL STATUS
# =========================================================

@app.get("/api/v1/status")
async def status():

    return {
        "status": "online",
        "market": "QUOTEX",
        "email_configured": bool(QUOTEX_EMAIL),
        "password_configured": bool(QUOTEX_PASSWORD),
        "client_created": client is not None
    }


# =========================================================
# AVAILABLE PAIRS
# =========================================================

@app.get("/api/v1/pairs")
async def available_pairs():

    return {
        "status": "success",
        "market": "QUOTEX",
        "data": "REAL",
        "pairs": PAIRS,
        "count": len(PAIRS)
    }


# =========================================================
# QUOTEX CONNECTION TEST
# =========================================================

@app.get("/api/v1/quotex-status")
async def quotex_status():

    try:

        q = await get_client()

        connected = await q.check_connect()

        return {
            "status": "success" if connected else "error",
            "market": "QUOTEX",
            "data": "REAL",
            "connected": connected,
            "message": (
                "Quotex connection is active"
                if connected
                else "Quotex connection is not active"
            )
        }

    except Exception as e:

        logger.exception(
            "Quotex status check failed"
        )

        return {
            "status": "error",
            "market": "QUOTEX",
            "data": "REAL",
            "connected": False,
            "message": str(e)
        }


# =========================================================
# SINGLE PAIR CANDLES
# =========================================================

@app.get("/api/v1/candles")
async def candles(

    symbol: str = Query(
        "EURUSD",
        description="Quotex symbol"
    ),

    timeframe: str = Query(
        "M1",
        description="M1 or M5"
    )

):

    symbol = symbol.strip().upper()
    timeframe = timeframe.strip().upper()

    # Timeframe
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

        logger.info(
            "Candle request: %s | %s",
            symbol,
            timeframe
        )

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
            "count": len(candles_data[-100:]),
            "candles": candles_data[-100:]
        }

    except Exception as e:

        logger.exception(
            "Candle request failed"
        )

        return {
            "status": "error",
            "market": "QUOTEX",
            "data": "REAL",
            "symbol": symbol,
            "timeframe": timeframe,
            "message": str(e)
        }


# =========================================================
# ALL PAIRS
# =========================================================

@app.get("/api/v1/all-candles")
async def all_candles(

    timeframe: str = Query(
        "M1"
    )

):

    timeframe = timeframe.strip().upper()

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

            logger.info(
                "Loading pair: %s",
                symbol
            )

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
                    "message": "No real candles"
                }

        except Exception as e:

            logger.exception(
                "Pair failed: %s",
                symbol
            )

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


# =========================================================
# SHUTDOWN
# =========================================================

@app.on_event("shutdown")
async def shutdown():

    global client

    if client is not None:

        try:

            await client.close()

        except Exception as e:

            logger.warning(
                "Error closing Quotex: %s",
                str(e)
            )

        client = None
