import os
import time
import traceback

import curl_cffi.requests

# Compatibility fix for pyquotex
Response = curl_cffi.requests.Response

if not hasattr(Response, "reason_phrase"):
    Response.reason_phrase = property(
        lambda self: getattr(self, "reason", "")
    )

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pyquotex.stable_api import Quotex


app = FastAPI()


# CORS - allows your Netlify website to call this backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Credentials are taken from Render Environment Variables
EMAIL = os.getenv("QUOTEX_EMAIL")
PASSWORD = os.getenv("QUOTEX_PASSWORD")


# --------------------------------------------------
# HOME / STATUS
# --------------------------------------------------

@app.get("/")
def home():
    return {
        "status": "online",
        "message": "Quotex OTC Backend Running",
        "market": "QUOTEX_OTC",
        "timeframe": "M1"
    }


# --------------------------------------------------
# QUOTEX OTC M1 CANDLES
# --------------------------------------------------

@app.get("/api/v1/candles")
async def candles(symbol: str = "EURUSD_otc"):

    if not EMAIL:
        raise HTTPException(
            status_code=500,
            detail="QUOTEX_EMAIL is missing in Render Environment Variables"
        )

    if not PASSWORD:
        raise HTTPException(
            status_code=500,
            detail="QUOTEX_PASSWORD is missing in Render Environment Variables"
        )

    client = None

    try:

        print("====================================")
        print("Starting Quotex connection...")
        print("Symbol:", symbol)
        print("Timeframe: M1")
        print("====================================")

        # Create Quotex client
        client = Quotex(
            email=EMAIL,
            password=PASSWORD,
            lang="en"
        )

        # Connect to Quotex
        connected, reason = await client.connect()

        print("Connection result:", connected)
        print("Connection message:", reason)

        if not connected:
            raise HTTPException(
                status_code=401,
                detail=f"Quotex connection failed: {reason}"
            )

        print("Quotex connection successful")

        # Current time
        end_time = time.time()

        # Get recent 1-minute candles
        data = await client.get_candles(
            asset=symbol,
            end_from_time=end_time,
            offset=60 * 200,
            period=60
        )

        if not data:
            raise HTTPException(
                status_code=404,
                detail=f"No candles returned for {symbol}"
            )

        print("Candles received:", len(data))

        candles_result = []

        for candle in data:

            candles_result.append({
                "time": candle.get("time"),
                "open": candle.get("open"),
                "high": candle.get("high"),
                "low": candle.get("low"),
                "close": candle.get("close"),
                "ticks": candle.get("ticks", 0)
            })

        return {
            "status": "success",
            "market": "QUOTEX_OTC",
            "symbol": symbol,
            "timeframe": "M1",
            "count": len(candles_result),
            "candles": candles_result
        }

    except HTTPException:
        raise

    except Exception as e:

        print("")
        print("====================================")
        print("        QUOTEX API ERROR")
        print("====================================")
        print("Error type:", type(e).__name__)
        print("Error:", str(e))
        print("")
        print("FULL TRACEBACK:")
        print(traceback.format_exc())
        print("====================================")

        raise HTTPException(
            status_code=500,
            detail=f"{type(e).__name__}: {str(e)}"
        )

    finally:

        if client:

            try:
                await client.close()
                print("Quotex connection closed")

            except Exception as close_error:
                print(
                    "Close connection error:",
                    str(close_error)
                )
