import os
import sys
import time
import importlib.metadata

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


# --------------------------------------------------
# HOME
# --------------------------------------------------

@app.get("/")
def home():
    return {
        "status": "online",
        "market": "QUOTEX_OTC",
        "timeframe": "M1",
        "message": "Quotex OTC Live Market Data Backend",
        "pairs": OTC_PAIRS
    }


# --------------------------------------------------
# DIAGNOSTICS
# --------------------------------------------------

@app.get("/api/v1/diagnostics")
async def diagnostics():

    def get_version(package_name):
        try:
            return importlib.metadata.version(package_name)
        except Exception:
            return "not-installed"

    return {
        "status": "diagnostic",
        "python_version": sys.version,
        "python_major": sys.version_info.major,
        "python_minor": sys.version_info.minor,

        "pyquotex_version": get_version("pyquotex"),
        "curl_cffi_version": get_version("curl_cffi"),
        "httpx_version": get_version("httpx"),
        "fastapi_version": get_version("fastapi"),
        "uvicorn_version": get_version("uvicorn"),

        "quotex_email_configured": bool(os.getenv("QUOTEX_EMAIL")),
        "quotex_password_configured": bool(os.getenv("QUOTEX_PASSWORD")),

        "market": "QUOTEX_OTC",
        "timeframe": "M1"
    }


# --------------------------------------------------
# CREATE QUOTEX CLIENT
# --------------------------------------------------

def create_client():

    email = os.getenv("QUOTEX_EMAIL")
    password = os.getenv("QUOTEX_PASSWORD")

    if not email or not password:
        raise RuntimeError(
            "QUOTEX_EMAIL / QUOTEX_PASSWORD missing"
        )

    client = Quotex(
        email=email,
        password=password,
        lang="en"
    )

    return client


# --------------------------------------------------
# STATUS
# --------------------------------------------------

@app.get("/api/v1/status")
async def status():

    try:

        email = os.getenv("QUOTEX_EMAIL")
        password = os.getenv("QUOTEX_PASSWORD")

        if not email or not password:
            return {
                "status": "error",
                "market": "QUOTEX_OTC",
                "timeframe": "M1",
                "connection": "NOT_CONFIGURED",
                "error": "QUOTEX_CREDENTIALS_MISSING"
            }

        client = create_client()

        try:

            if hasattr(client, "debug_ws_enable"):
                client.debug_ws_enable = True

            connected, message = await client.connect()

            return {
                "status": "online" if connected else "error",
                "market": "QUOTEX_OTC",
                "timeframe": "M1",
                "connection": "CONNECTED" if connected else "FAILED",
                "message": str(message)
            }

        finally:

            try:
                await client.close()
            except Exception:
                pass

    except Exception as e:

        return {
            "status": "error",
            "market": "QUOTEX_OTC",
            "timeframe": "M1",
            "connection": "FAILED",
            "error": type(e).__name__,
            "message": repr(e)
        }


# --------------------------------------------------
# OTC CANDLES
# --------------------------------------------------

@app.get("/api/v1/candles")
async def candles(symbol: str = "AUDNZD_otc"):

    if symbol not in OTC_PAIRS:
        return {
            "status": "error",
            "market": "QUOTEX_OTC",
            "symbol": symbol,
            "timeframe": "M1",
            "error": "INVALID_OTC_SYMBOL",
            "message": "Symbol is not in the configured OTC pair list",
            "candles": []
        }

    client = None

    try:

        client = create_client()

        if hasattr(client, "debug_ws_enable"):
            client.debug_ws_enable = True

        connected, message = await client.connect()

        if not connected:
            return {
                "status": "error",
                "market": "QUOTEX_OTC",
                "symbol": symbol,
                "timeframe": "M1",
                "connection": "FAILED",
                "error": "OTC_CONNECTION_FAILED",
                "message": str(message),
                "candles": []
            }

        # Start 1-minute realtime candle stream
        await client.start_candles_one_stream(
            symbol,
            60
        )

        # Give the stream a moment to receive data
        await asyncio_sleep(3)

        realtime = await client.get_realtime_candles(
            symbol,
            60
        )

        if not realtime:
            return {
                "status": "error",
                "market": "QUOTEX_OTC",
                "symbol": symbol,
                "timeframe": "M1",
                "connection": "CONNECTED",
                "error": "NO_REALTIME_CANDLES",
                "message": "Connected but no realtime OTC candles were returned",
                "candles": []
            }

        candles_list = []

        if isinstance(realtime, dict):

            items = realtime.items()

            for timestamp, candle in items:

                if isinstance(candle, dict):

                    candles_list.append({
                        "time": timestamp,
                        "open": candle.get("open"),
                        "high": candle.get("high"),
                        "low": candle.get("low"),
                        "close": candle.get("close"),
                        "volume": candle.get("volume", 0)
                    })

        candles_list.sort(
            key=lambda x: float(x["time"])
            if str(x["time"]).replace(".", "", 1).isdigit()
            else 0
        )

        return {
            "status": "success",
            "market": "QUOTEX_OTC",
            "symbol": symbol,
            "timeframe": "M1",
            "connection": "CONNECTED",
            "count": len(candles_list),
            "candles": candles_list
        }

    except Exception as e:

        return {
            "status": "error",
            "market": "QUOTEX_OTC",
            "symbol": symbol,
            "timeframe": "M1",
            "connection": "FAILED",
            "error": "OTC_CONNECTION_OR_CANDLE_ERROR",
            "message": repr(e),
            "candles": []
        }

    finally:

        if client is not None:

            try:
                await client.close()
            except Exception:
                pass


# --------------------------------------------------
# SMALL ASYNC SLEEP HELPER
# --------------------------------------------------

async def asyncio_sleep(seconds):
    import asyncio
    await asyncio.sleep(seconds)
