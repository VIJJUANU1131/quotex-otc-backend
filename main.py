import os
import time
import traceback

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from pyquotex.network.login import Login
from pyquotex.stable_api import Quotex


# ==================================================
# FIX pyquotex reason_phrase ERROR
# ==================================================

_original_login_call = Login.__call__


async def fixed_login_call(self, username, password, user_data_dir=None):
    try:
        home = await self.get_sign_page()

        if not home.is_success:
            reason = getattr(
                home,
                "reason",
                f"HTTP {getattr(home, 'status_code', 'unknown')}"
            )

            print("===== QUOTEX LOGIN PAGE ERROR =====")
            print("Status:", getattr(home, "status_code", "unknown"))
            print("Reason:", reason)
            print("URL:", getattr(home, "url", "unknown"))
            print("===================================")

            return False, f"Access page failed: {reason}"

        data = {
            "_token": await self.get_token(),
            "email": username,
            "password": password,
            "remember": 1,
        }

        status, msg = await self._post(data)

        return status, msg

    except Exception as e:
        print("===== LOGIN ERROR =====")
        print(traceback.format_exc())
        print("=======================")

        return False, f"{type(e).__name__}: {str(e)}"


Login.__call__ = fixed_login_call


# ==================================================
# FASTAPI
# ==================================================

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


EMAIL = os.getenv("QUOTEX_EMAIL")
PASSWORD = os.getenv("QUOTEX_PASSWORD")


# ==================================================
# HOME
# ==================================================

@app.get("/")
def home():
    return {
        "status": "online",
        "message": "Quotex OTC Backend Running",
        "market": "QUOTEX_OTC",
        "timeframe": "M1"
    }


# ==================================================
# OTC M1 CANDLES
# ==================================================

@app.get("/api/v1/candles")
async def candles(symbol: str = "EURUSD_otc"):

    if not EMAIL:
        raise HTTPException(
            status_code=500,
            detail="QUOTEX_EMAIL is missing"
        )

    if not PASSWORD:
        raise HTTPException(
            status_code=500,
            detail="QUOTEX_PASSWORD is missing"
        )

    client = None

    try:

        print("===================================")
        print("Connecting to Quotex...")
        print("Symbol:", symbol)
        print("Timeframe: M1")
        print("===================================")

        client = Quotex(
            email=EMAIL,
            password=PASSWORD,
            host="qxbroker.com",
            lang="en",
            asset_default=symbol,
            period_default=60
        )

        # Demo account
        client.set_account_mode("PRACTICE")

        connected, reason = await client.connect()

        print("Connected:", connected)
        print("Message:", reason)

        if not connected:
            raise HTTPException(
                status_code=401,
                detail=f"Quotex connection failed: {reason}"
            )

        # Current timestamp
        end_time = time.time()

        print("Requesting M1 candles...")

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

        print("Candles received:", len(result))

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

        print("")
        print("===================================")
        print("       QUOTEX API ERROR")
        print("===================================")
        print("Type:", type(e).__name__)
        print("Error:", str(e))
        print("")
        print(traceback.format_exc())
        print("===================================")

        raise HTTPException(
            status_code=500,
            detail=f"{type(e).__name__}: {str(e)}"
        )

    finally:

        if client:

            try:
                await client.close()
                print("Quotex connection closed")

            except Exception as e:
                print("Close error:", str(e))
