import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pyquotex.stable_api import Quotex


app = FastAPI(
    title="Quotex OTC Backend",
    version="1.0.0"
)


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


def make_client():

    email = os.getenv("QUOTEX_EMAIL")
    password = os.getenv("QUOTEX_PASSWORD")

    if not email or not password:
        return None

    client = Quotex(
        email=email,
        password=password,
        lang="en",
        host="qxbroker.com",
        asset_default="AUDNZD_otc",
        period_default=60
    )

    return client


@app.get("/")
async def home():

    return {
        "status": "online",
        "market": "QUOTEX_OTC",
        "timeframe": "M1",
        "data": "REAL_ONLY",
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
            "market": "QUOTEX_OTC",
            "error": "QUOTEX_CREDENTIALS_MISSING"
        }

    client = None

    try:

        client = make_client()

        if client is None:

            return {
                "status": "error",
                "connection": "NOT_CONFIGURED",
                "market": "QUOTEX_OTC",
                "error": "QUOTEX_CREDENTIALS_MISSING"
            }

        # Enable debug information in Render logs
        client.debug_ws_enable = True

        connected, message = await client.connect()

        if connected:

            return {
                "status": "online",
                "connection": "CONNECTED",
                "market": "QUOTEX_OTC",
                "timeframe": "M1",
                "message": str(message)
            }

        return {
            "status": "error",
            "connection": "FAILED",
            "market": "QUOTEX_OTC",
            "timeframe": "M1",
            "error": "QUOTEX_CONNECTION_FAILED",
            "message": str(message)
        }

    except Exception as e:

        error_text = repr(e)

        return {
            "status": "error",
            "connection": "FAILED",
            "market": "QUOTEX_OTC",
            "timeframe": "M1",
            "error": "QUOTEX_CONNECTION_EXCEPTION",
            "message": error_text
        }

    finally:

        if client:

            try:
                await client.close()
            except Exception:
                pass


@app.get("/api/v1/candles")
async def candles(
    symbol: str = "AUDNZD_otc"
):

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
            "market": "QUOTEX_OTC",
            "symbol": symbol,
            "timeframe": "M1",
            "error": "QUOTEX_CREDENTIALS_MISSING",
            "candles": []
        }

    client = None

    try:

        client = Quotex(
            email=email,
            password=password,
            lang="en",
            host="qxbroker.com",
            asset_default=symbol,
            period_default=60
        )

        client.debug_ws_enable = True

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

        # IMPORTANT:
        # This method is async in the current PyQuotex API.
        await client.start_candles_one_stream(
            symbol,
            60
        )

        # Wait for realtime candle data
        import asyncio
        await asyncio.sleep(3)

        data = await client.get_realtime_candles(
            symbol,
            60
        )

        if not data:

            return {
                "status": "error",
                "market": "QUOTEX_OTC",
                "symbol": symbol,
                "timeframe": "M1",
                "connection": "CONNECTED",
                "error": "NO_CANDLE_DATA",
                "message": "Connected but no real OTC candle data received",
                "candles": []
            }

        if isinstance(data, dict):

            values = list(data.values())

        elif isinstance(data, list):

            values = data

        else:

            values = []

        result = []

        for candle in values:

            if not isinstance(candle, dict):
                continue

            try:

                item = {
                    "time": (
                        candle.get("time")
                        or candle.get("timestamp")
                        or candle.get("from")
                    ),
                    "open": float(candle["open"]),
                    "high": float(candle["high"]),
                    "low": float(candle["low"]),
                    "close": float(candle["close"])
                }

                result.append(item)

            except Exception:

                continue

        result = result[-100:]

        price = None

        if result:
            price = result[-1]["close"]

        return {
            "status": "success",
            "market": "QUOTEX_OTC",
            "symbol": symbol,
            "timeframe": "M1",
            "connection": "CONNECTED",
            "data": "REAL",
            "price": price,
            "count": len(result),
            "candles": result
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

        if client:

            try:
                await client.close()
            except Exception:
                pass
