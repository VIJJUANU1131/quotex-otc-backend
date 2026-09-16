import os
import time
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pyquotex.stable_api import Quotex

app = FastAPI(title="Quotex OTC Live Market Data")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

OTC_PAIRS = [
    "AUDNZD_otc",
    "GBPNZD_otc",
    "NZDCAD_otc",
    "NZDUSD_otc",
    "USDBRL_otc",
    "USDDZD_otc",
    "USDEGP_otc",
    "USDNGN_otc",
    "USDCOP_otc",
    "USDBDT_otc",
    "USDPHP_otc",
]


@app.get("/")
def home():
    return {
        "status": "online",
        "market": "QUOTEX_OTC",
        "timeframe": "M1",
        "message": "Quotex OTC Live Market Data Backend",
        "pairs": OTC_PAIRS
    }


@app.get("/api/v1/status")
async def status():

    email = os.getenv("QUOTEX_EMAIL")
    password = os.getenv("QUOTEX_PASSWORD")

    if not email or not password:
        return {
            "status": "error",
            "connection": "NOT_CONFIGURED",
            "message": "QUOTEX_EMAIL / QUOTEX_PASSWORD missing"
        }

    client = Quotex(
        email=email,
        password=password,
        lang="en"
    )

    try:
        connected, message = await client.connect()

        return {
            "status": "online" if connected else "error",
            "connection": "CONNECTED" if connected else "FAILED",
            "market": "QUOTEX_OTC",
            "message": str(message)
        }

    except Exception as e:
        return {
            "status": "error",
            "connection": "FAILED",
            "error": str(e)
        }

    finally:
        try:
            await client.close()
        except:
            pass


@app.get("/api/v1/candles")
async def candles(symbol: str = "EURUSD_otc"):

    if symbol not in OTC_PAIRS:
        return {
            "status": "error",
            "market": "QUOTEX_OTC",
            "symbol": symbol,
            "timeframe": "M1",
            "error": "UNSUPPORTED_OTC_PAIR",
            "candles": []
        }

    email = os.getenv("QUOTEX_EMAIL")
    password = os.getenv("QUOTEX_PASSWORD")

    if not email or not password:
        return {
            "status": "error",
            "error": "QUOTEX_CREDENTIALS_MISSING",
            "candles": []
        }

    client = Quotex(
        email=email,
        password=password,
        lang="en"
    )

    try:

        connected, message = await client.connect()

        if not connected:
            return {
                "status": "error",
                "market": "QUOTEX_OTC",
                "symbol": symbol,
                "timeframe": "M1",
                "connection": "FAILED",
                "error": "QUOTEX_CONNECTION_FAILED",
                "message": str(message),
                "candles": []
            }

        # 1-minute realtime candle stream
        client.start_candles_stream(symbol, 60)

        # Give websocket a moment to receive data
        await __import__("asyncio").sleep(2)

        data = await client.get_realtime_candles(symbol, 60)

        if not data:
            return {
                "status": "error",
                "market": "QUOTEX_OTC",
                "symbol": symbol,
                "timeframe": "M1",
                "connection": "CONNECTED",
                "error": "NO_CANDLE_DATA",
                "message": "Connected to Quotex but no OTC candle data received",
                "candles": []
            }

        candles_list = []

        if isinstance(data, dict):
            values = list(data.values())
        else:
            values = data

        for candle in values:

            if not isinstance(candle, dict):
                continue

            item = {
                "time": candle.get("time"),
                "open": candle.get("open"),
                "high": candle.get("high"),
                "low": candle.get("low"),
                "close": candle.get("close")
            }

            if item["close"] is not None:
                candles_list.append(item)

        candles_list = candles_list[-100:]

        latest_price = None

        if candles_list:
            latest_price = candles_list[-1]["close"]

        return {
            "status": "success",
            "market": "QUOTEX_OTC",
            "symbol": symbol,
            "timeframe": "M1",
            "connection": "CONNECTED",
            "price": latest_price,
            "count": len(candles_list),
            "candles": candles_list
        }

    except Exception as e:

        return {
            "status": "error",
            "market": "QUOTEX_OTC",
            "symbol": symbol,
            "timeframe": "M1",
            "error": "OTC_DATA_ERROR",
            "message": str(e),
            "candles": []
        }

    finally:

        try:
            await client.close()
        except:
            pass
