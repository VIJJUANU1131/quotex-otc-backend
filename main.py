import os
import time

import curl_cffi.requests

if not hasattr(curl_cffi.requests.Response, "reason_phrase"):
    curl_cffi.requests.Response.reason_phrase = property(
        lambda self: getattr(self, "reason", "")
    )
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import curl_cffi.requests
from pyquotex.stable_api import Quotex

app = FastAPI()

# Allow Netlify frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

EMAIL = os.getenv("QUOTEX_EMAIL")
PASSWORD = os.getenv("QUOTEX_PASSWORD")


@app.get("/")
def home():
    return {
        "status": "online",
        "message": "Quotex OTC Backend Running",
        "market": "QUOTEX_OTC",
        "timeframe": "M1"
    }


@app.get("/api/v1/candles")
async def candles(symbol: str = "EURUSD_otc"):
    if not EMAIL or not PASSWORD:
        raise HTTPException(
            status_code=500,
            detail="QUOTEX_EMAIL or QUOTEX_PASSWORD is missing"
        )

    client = None

    try:
        client = Quotex(
            email=EMAIL,
            password=PASSWORD,
            lang="en",
            asset_default=symbol,
            period_default=60
        )

        # Demo account connection
        connected, reason = await client.connect()

        if not connected:
            raise HTTPException(
                status_code=401,
                detail=f"Quotex connection failed: {reason}"
            )

        # Get recent 1-minute candles
        end_time = time.time()

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

        result = []

        for candle in data:
            result.append({
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
            "count": len(result),
            "candles": result
        }

        except HTTPException:
        raise

    except Exception as e:
        import traceback

        print("===== QUOTEX ERROR =====")
        print(traceback.format_exc())
        print("========================")

        raise HTTPException(
            status_code=500,
            detail=f"Quotex API error: {type(e).__name__}: {str(e)}"
        )

    finally:
        if client:
            try:
                await client.close()
            except Exception:
                pass
