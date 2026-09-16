import os
import asyncio

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from pyquotex.stable_api import Quotex


# ==================================================
# APP
# ==================================================

app = FastAPI(
    title="Quotex OTC Live Signal Backend",
    version="1.0.0"
)


# ==================================================
# CORS
# ==================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==================================================
# OTC PAIRS
# ==================================================

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


# ==================================================
# CREATE QUOTEX CLIENT
# ==================================================

def create_client():

    email = os.getenv("QUOTEX_EMAIL")
    password = os.getenv("QUOTEX_PASSWORD")

    if not email or not password:
        return None

    return Quotex(
        email=email,
        password=password,
        lang="en"
    )


# ==================================================
# HOME
# ==================================================

@app.get("/")
async def home():

    return {
        "status": "online",
        "market": "QUOTEX_OTC",
        "timeframe": "M1",
        "data": "REAL_ONLY",
        "message": "Quotex OTC Live Market Backend",
        "pairs": OTC_PAIRS
    }


# ==================================================
# STATUS
# ==================================================

@app.get("/api/v1/status")
async def status():

    email = os.getenv("QUOTEX_EMAIL")
    password = os.getenv("QUOTEX_PASSWORD")

    # ----------------------------------------------
    # CHECK ENVIRONMENT
    # ----------------------------------------------

    if not email or not password:

        return {
            "status": "error",
            "connection": "NOT_CONFIGURED",
            "market": "QUOTEX_OTC",
            "timeframe": "M1",
            "error": "QUOTEX_CREDENTIALS_MISSING",
            "message": "QUOTEX_EMAIL or QUOTEX_PASSWORD is missing"
        }


    client = None

    try:

        client = create_client()

        if client is None:

            return {
                "status": "error",
                "connection": "NOT_CONFIGURED",
                "market": "QUOTEX_OTC",
                "timeframe": "M1",
                "error": "QUOTEX_CREDENTIALS_MISSING"
            }


        # ------------------------------------------
        # CONNECT
        # ------------------------------------------

        connected, message = await client.connect()


        if connected:

            return {
                "status": "online",
                "connection": "CONNECTED",
                "market": "QUOTEX_OTC",
                "timeframe": "M1",
                "data": "REAL",
                "message": str(message)
            }


        error_text = str(message)


        if "403" in error_text:

            return {
                "status": "error",
                "connection": "BLOCKED",
                "market": "QUOTEX_OTC",
                "timeframe": "M1",
                "error": "QUOTEX_HTTP_403",
                "message": "Quotex rejected the connection with HTTP 403",
                "details": error_text
            }


        return {
            "status": "error",
            "connection": "FAILED",
            "market": "QUOTEX_OTC",
            "timeframe": "M1",
            "error": "QUOTEX_CONNECTION_FAILED",
            "message": error_text
        }


    except Exception as e:

        error_text = str(e)


        # ------------------------------------------
        # 403 / RESPONSE ERROR
        # ------------------------------------------

        if (
            "403" in error_text
            or "reason_phrase" in error_text
        ):

            return {
                "status": "error",
                "connection": "BLOCKED",
                "market": "QUOTEX_OTC",
                "timeframe": "M1",
                "error": "QUOTEX_ACCESS_BLOCKED",
                "message": (
                    "Quotex connection was rejected. "
                    "Real OTC data is not available from this connection."
                ),
                "details": error_text
            }


        return {
            "status": "error",
            "connection": "FAILED",
            "market": "QUOTEX_OTC",
            "timeframe": "M1",
            "error": "QUOTEX_CONNECTION_ERROR",
            "message": error_text
        }


    finally:

        if client:

            try:
                await client.close()
            except Exception:
                pass


# ==================================================
# REAL OTC M1 CANDLES
# ==================================================

@app.get("/api/v1/candles")
async def candles(
    symbol: str = "AUDNZD_otc"
):

    # ----------------------------------------------
    # CHECK SYMBOL
    # ----------------------------------------------

    if symbol not in OTC_PAIRS:

        return {
            "status": "error",
            "market": "QUOTEX_OTC",
            "symbol": symbol,
            "timeframe": "M1",
            "error": "UNSUPPORTED_OTC_PAIR",
            "message": "Unsupported OTC pair",
            "candles": []
        }


    # ----------------------------------------------
    # CHECK LOGIN
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
            "message": "Quotex credentials are missing",
            "candles": []
        }


    client = None

    try:

        # ------------------------------------------
        # CLIENT
        # ------------------------------------------

        client = create_client()


        # ------------------------------------------
        # CONNECT
        # ------------------------------------------

        connected, message = await client.connect()


        if not connected:

            error_text = str(message)


            if "403" in error_text:

                return {
                    "status": "error",
                    "market": "QUOTEX_OTC",
                    "symbol": symbol,
                    "timeframe": "M1",
                    "connection": "BLOCKED",
                    "error": "QUOTEX_HTTP_403",
                    "message": "Quotex returned HTTP 403",
                    "details": error_text,
                    "candles": []
                }


            return {
                "status": "error",
                "market": "QUOTEX_OTC",
                "symbol": symbol,
                "timeframe": "M1",
                "connection": "FAILED",
                "error": "QUOTEX_CONNECTION_FAILED",
                "message": error_text,
                "candles": []
            }


        # ------------------------------------------
        # START M1 STREAM
        # ------------------------------------------

        try:

            result = client.start_candles_one_stream(
                symbol,
                60
            )

            # Support both sync and async versions
            if asyncio.iscoroutine(result):
                await result

        except Exception as e:

            error_text = str(e)

            return {
                "status": "error",
                "market": "QUOTEX_OTC",
                "symbol": symbol,
                "timeframe": "M1",
                "connection": "CONNECTED",
                "error": "CANDLE_STREAM_ERROR",
                "message": error_text,
                "candles": []
            }


        # ------------------------------------------
        # WAIT FOR REAL DATA
        # ------------------------------------------

        await asyncio.sleep(3)


        # ------------------------------------------
        # GET REALTIME CANDLES
        # ------------------------------------------

        data = client.get_realtime_candles(
            symbol,
            60
        )

        # Support async/sync versions
        if asyncio.iscoroutine(data):
            data = await data


        if not data:

            return {
                "status": "error",
                "market": "QUOTEX_OTC",
                "symbol": symbol,
                "timeframe": "M1",
                "connection": "CONNECTED",
                "error": "NO_CANDLE_DATA",
                "message": "No real OTC M1 candle data received",
                "candles": []
            }


        # ------------------------------------------
        # NORMALIZE DATA
        # ------------------------------------------

        candles_list = []


        if isinstance(data, dict):

            values = list(data.values())

        elif isinstance(data, list):

            values = data

        else:

            values = []


        # ------------------------------------------
        # PROCESS CANDLES
        # ------------------------------------------

        for candle in values:

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
                or candle.get("high_price")
                or candle.get("max")
            )


            low_price = (
                candle.get("low")
                or candle.get("low_price")
                or candle.get("min")
            )


            close_price = (
                candle.get("close")
                or candle.get("close_price")
            )


            if close_price is None:
                continue


            try:

                item = {
                    "time": candle_time,
                    "open": (
                        float(open_price)
                        if open_price is not None
                        else None
                    ),
                    "high": (
                        float(high_price)
                        if high_price is not None
                        else None
                    ),
                    "low": (
                        float(low_price)
                        if low_price is not None
                        else None
                    ),
                    "close": float(close_price)
                }


                candles_list.append(item)


            except Exception:

                continue


        # ------------------------------------------
        # SORT
        # ------------------------------------------

        def get_time(item):

            value = item.get("time")

            try:
                return float(value)
            except Exception:
                return 0


        candles_list.sort(
            key=get_time
        )


        # ------------------------------------------
        # LAST 100
        # ------------------------------------------

        candles_list = candles_list[-100:]


        # ------------------------------------------
        # PRICE
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
        # ACCESS / RESPONSE ERROR
        # ------------------------------------------

        if (
            "403" in error_text
            or "reason_phrase" in error_text
        ):

            return {
                "status": "error",
                "market": "QUOTEX_OTC",
                "symbol": symbol,
                "timeframe": "M1",
                "connection": "BLOCKED",
                "error": "QUOTEX_ACCESS_BLOCKED",
                "message": (
                    "Quotex rejected the connection. "
                    "No real OTC candle was generated."
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
            "connection": "FAILED",
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

                result = client.stop_candles_one_stream(
                    symbol,
                    60
                )

                if asyncio.iscoroutine(result):
                    await result

            except Exception:
                pass


            # --------------------------------------
            # CLOSE
            # --------------------------------------

            try:

                await client.close()

            except Exception:
                pass
