import os
import asyncio
import logging
import traceback
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

logger = logging.getLogger("quotex")


# =========================================================
# APP
# =========================================================

app = FastAPI(
    title="Quotex Real Market API",
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
# ENVIRONMENT
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
# CREATE QUOTEX CLIENT
# =========================================================

def create_client():

    if not QUOTEX_EMAIL:
        raise RuntimeError(
            "QUOTEX_EMAIL is missing"
        )

    if not QUOTEX_PASSWORD:
        raise RuntimeError(
            "QUOTEX_PASSWORD is missing"
        )

    logger.info("Creating Quotex client")

    q = Quotex(
        email=QUOTEX_EMAIL,
        password=QUOTEX_PASSWORD,
        host="qxbroker.com",
        lang="en",
        asset_default="EURUSD",
        period_default=60,
    )

    # Official PyQuotex debug option
    q.debug_ws_enable = True

    return q


# =========================================================
# CONNECT
# =========================================================

async def get_client():

    global client

    async with client_lock:

        # Existing client
        if client is not None:

            try:

                connected = await client.check_connect()

                if connected:
                    return client

            except Exception as e:

                logger.warning(
                    "Existing client check failed: %s",
                    str(e)
                )

        # New client
        client = create_client()

        logger.info(
            "Starting Quotex authentication..."
        )

        try:

            connected, reason = await client.connect()

            logger.info(
                "Connect result: connected=%s reason=%s",
                connected,
                reason
            )

            if not connected:

                raise RuntimeError(
                    f"Quotex connection failed: {reason}"
                )

            return client

        except Exception as e:

            logger.error(
                "QUOTEX CONNECTION ERROR: %s",
                str(e)
            )

            logger.error(
                traceback.format_exc()
            )

            client = None

            raise


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
        "python": "3.12+",
        "debug": True
    }


# =========================================================
# CONFIG STATUS
# =========================================================

@app.get("/api/v1/status")
async def config_status():

    return {
        "status": "online",
        "market": "QUOTEX",
        "email_configured": bool(QUOTEX_EMAIL),
        "password_configured": bool(QUOTEX_PASSWORD),
        "client_created": client is not None
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
                "Quotex connection successful"
                if connected
                else "Quotex connection not active"
            )
        }

    except Exception as e:

        logger.error(
            "Quotex status check failed"
        )

        logger.error(
            traceback.format_exc()
        )

        return {
            "status": "error",
            "market": "QUOTEX",
            "data": "REAL",
            "connected": False,
            "error_type": type(e).__name__,
            "message": str(e)
        }


# =========================================================
# PAIRS
# =========================================================

@app.get("/api/v1/pairs")
async def pairs():

    return {
        "status": "success",
        "market": "QUOTEX",
        "data": "REAL",
        "count": len(PAIRS),
        "pairs": PAIRS
    }


# =========================================================
# CANDLE NORMALIZER
# =========================================================

def normalize_candles(raw) -> List[dict]:

    result = []

    if not raw:
        return result

    if isinstance(raw, dict):

        items = raw.items()

    elif isinstance(raw, list):

        items = enumerate(raw)

    else:

        return result

    for timestamp, candle in items:

        if not isinstance(candle, dict):
            continue

        try:

            epoch = int(float(timestamp))

        except Exception:

            continue

        try:

            open_price = float(
                candle.get(
                    "open",
                    candle.get("Open", 0)
                )
            )

            high_price = float(
                candle.get(
                    "high",
                    candle.get("High", 0)
                )
            )

            low_price = float(
                candle.get(
                    "low",
                    candle.get("Low", 0)
                )
            )

            close_price = float(
                candle.get(
                    "close",
                    candle.get("Close", 0)
                )
            )

        except Exception:

            continue

        if open_price == 0 and close_price == 0:
            continue

        result.append({
            "epoch": epoch,
            "open": open_price,
            "high": high_price,
            "low": low_price,
            "close": close_price
        })

    result.sort(
        key=lambda x: x["epoch"]
    )

    return result


# =========================================================
# GET CANDLES
# =========================================================

async def get_real_candles(
    symbol: str,
    period: int
):

    q = await get_client()

    logger.info(
        "Starting candle stream: %s / %s seconds",
        symbol,
        period
    )

    await q.start_candles_stream(
        symbol,
        period
    )

    await asyncio.sleep(2)

    raw = await q.get_realtime_candles(
        symbol,
        period
    )

    candles = normalize_candles(raw)

    logger.info(
        "Candles received: %s = %s",
        symbol,
        len(candles)
    )

    return candles


# =========================================================
# SINGLE CANDLE ENDPOINT
# =========================================================

@app.get("/api/v1/candles")
async def candles(

    symbol: str = Query(
        "EURUSD"
    ),

    timeframe: str = Query(
        "M1"
    )

):

    symbol = symbol.strip().upper()
    timeframe = timeframe.strip().upper()

    if timeframe == "M1":

        period = 60

    elif timeframe == "M5":

        period = 300

    else:

        return {
            "status": "error",
            "message": "Only M1 and M5 are supported"
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
            "count": len(candles_data[-100:]),
            "candles": candles_data[-100:]
        }

    except Exception as e:

        logger.error(
            "Candle error: %s",
            str(e)
        )

        logger.error(
            traceback.format_exc()
        )

        return {
            "status": "error",
            "market": "QUOTEX",
            "data": "REAL",
            "symbol": symbol,
            "timeframe": timeframe,
            "error_type": type(e).__name__,
            "message": str(e)
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

        except Exception:

            pass

        client = None

@app.get("/api/v1/debug-versions")
async def debug_versions():
    import sys
    import curl_cffi
    import pyquotex

    return {
        "python": sys.version,
        "curl_cffi": getattr(curl_cffi, "__version__", "unknown"),
        "pyquotex": getattr(pyquotex, "__version__", "unknown")
    }
