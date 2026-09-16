import os
import asyncio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from pyquotex.stable_api import Quotex


app = FastAPI(
    title="Quotex OTC Live Signal Backend",
    version="1.0.0"
)

# --------------------------------------------------
# CORS
# --------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --------------------------------------------------
# QUOTEX OTC PAIRS
# --------------------------------------------------

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
async def home():

    return {
        "status": "online",
        "market": "QUOTEX_OTC",
        "timeframe": "M1",
        "data": "REAL",
        "message": "Quotex OTC Live Market Backend",
        "pairs": OTC_PAIRS
    }


# --------------------------------------------------
# STATUS
# --------------------------------------------------

@app.get("/api/v1/status")
async def status():

    email = os.getenv("QUOTEX_EMAIL")
    password = os.getenv("QUOTEX_PASSWORD")

    if not email or not password:

        return {
            "status": "error",
            "connection": "NOT_CONFIGURED",
            "market": "QUOTEX_OTC",
            "error": "QUOTEX_CREDENTIALS_MISSING",
            "message": "Add QUOTEX_EMAIL and QUOTEX_PASSWORD in Render Environment Variables"
        }

    client = None

    try:

        client = Quotex(
    email=email,
    password=password,
    lang="en",
    host="quotex.com"
        )

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
            "error": "QUOTEX_CONNECTION_FAILED",
            "message": str(message)
        }

    except Exception as e:

        return {
            "status": "error",
            "connection": "FAILED",
            "market": "QUOTEX_OTC",
            "error": "QUOTEX_CONNECTION_ERROR",
            "message": str(e)
        }

    finally:

        if client:

            try:
                await client.close()
            except Exception:
                pass


# --------------------------------------------------
# REAL OTC M1 CANDLES
# --------------------------------------------------

@app.get("/api/v1/candles")
async def candles(
    symbol: str = "AUDNZD_otc"
):

    # ----------------------------------------------
    # CHECK PAIR
    # ----------------------------------------------

    if symbol not in OTC_PAIRS:

        return {
            "status": "error",
            "market": "QUOTEX_OTC",
            "symbol": symbol,
            "timeframe": "M1",
            "error": "UNSUPPORTED_OTC_PAIR",
            "message": "This OTC pair is not enabled",
            "candles": []
        }


    # ----------------------------------------------
    # GET LOGIN
    # ----------------------------------------------

    email = os.getenv("QUOTEX_EMAIL")
    password = os.getenv("QUOTEX_PASSWORD")

    if not email or not password:

        return {
            "status": "error",
            "market": "QUOTEX_OTC",
            "symbol": symbol,
            "timeframe": "M1",
            "error": "QUOTEX_CREDENTIALS_MISSING",
            "message": "QUOTEX_EMAIL / QUOTEX_PASSWORD missing",
            "candles": []
        }


    client = None

    try:

        # ------------------------------------------
        # CREATE CLIENT
        # ------------------------------------------

        client = Quotex(
            email=email,
            password=password,
            lang="en",
            asset_default=symbol,
            period_default=60
        )


        # ------------------------------------------
        # CONNECT
        # ------------------------------------------

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


        # ------------------------------------------
        # START M1 CANDLE STREAM
        # ------------------------------------------

        await client.start_candles_one_stream(
            symbol,
            60
        )


        # ------------------------------------------
        # WAIT FOR DATA
        # ------------------------------------------

        await asyncio.sleep(3)


        # ------------------------------------------
        # GET REALTIME CANDLES
        # ------------------------------------------

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
                "message": "Quotex connected but no realtime OTC candle data was received",
                "candles": []
            }


        # ------------------------------------------
        # NORMALIZE DATA
        # ------------------------------------------

        candles_list = []


        if isinstance(data, dict):

            items = []

            for key, value in data.items():

                if isinstance(value, dict):

                    candle = dict(value)

                    if candle.get("time") is None:

                        candle["time"] = key

                    items.append(candle)

        elif isinstance(data, list):

            items = data

        else:

            items = []


        # ------------------------------------------
        # CONVERT CANDLE FIELDS
        # ------------------------------------------

        for candle in items:

            if not isinstance(candle, dict):
                continue


            candle_time = (
                candle.get("time")
                or candle.get("timestamp")
                or candle.get("from")
            )


            open_price = (
                candle.get("open")
                or candle.get("open_price")
            )


            high_price = (
                candle.get("high")
                or candle.get("max")
                or candle.get("high_price")
            )


            low_price = (
                candle.get("low")
                or candle.get("min")
                or candle.get("low_price")
            )


            close_price = (
                candle.get("close")
                or candle.get("close_price")
            )


            if close_price is None:
                continue


            try:

                normalized = {
                    "time": candle_time,
                    "open": float(open_price) if open_price is not None else None,
                    "high": float(high_price) if high_price is not None else None,
                    "low": float(low_price) if low_price is not None else None,
                    "close": float(close_price)
                }

                candles_list.append(normalized)

            except Exception:

                continue


        # ------------------------------------------
        # SORT BY TIME
        # ------------------------------------------

        def candle_sort(item):

            value = item.get("time")

            try:
                return float(value)
            except Exception:
                return 0


        candles_list.sort(
            key=candle_sort
        )


        # ------------------------------------------
        # KEEP LAST 100
        # ------------------------------------------

        candles_list = candles_list[-100:]


        # ------------------------------------------
        # LATEST PRICE
        # ------------------------------------------

        latest_price = None

        if candles_list:

            latest_price = candles_list[-1]["close"]


        # ------------------------------------------
        # SUCCESS
        # ------------------------------------------

        return {
            "status": "success",
            "market": "QUOTEX_OTC",
            "symbol": symbol,
            "timeframe": "M1",
            "connection": "CONNECTED",
            "data": "REAL",
            "price": latest_price,
            "count": len(candles_list),
            "candles": candles_list
        }


    except Exception as e:

        error_text = str(e)


        # ------------------------------------------
        # SPECIAL 403 MESSAGE
        # ------------------------------------------

        if "403" in error_text:

            return {
                "status": "error",
                "market": "QUOTEX_OTC",
                "symbol": symbol,
                "timeframe": "M1",
                "error": "QUOTEX_HTTP_403",
                "message": (
                    "Quotex connection returned HTTP 403. "
                    "This is an access/connection restriction, "
                    "not a candle-analysis error."
                ),
                "details": error_text,
                "candles": []
            }


        # ------------------------------------------
        # OTHER ERROR
        # ------------------------------------------

        return {
            "status": "error",
            "market": "QUOTEX_OTC",
            "symbol": symbol,
            "timeframe": "M1",
            "error": "OTC_DATA_ERROR",
            "message": error_text,
            "candles": []
        }


    finally:

        # ------------------------------------------
        # STOP STREAM
        # ------------------------------------------

        if client:

            try:

                await client.stop_candles_one_stream(
                    symbol,
                    60
                )

            except Exception:

                pass


            # --------------------------------------
            # CLOSE CONNECTION
            # --------------------------------------

            try:

                await client.close()

            except Exception:

                pass
