from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os
import requests
from datetime import datetime, timezone

app = FastAPI(title="Live Forex Signal Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

API_KEY = os.getenv("ALPHAVANTAGE_API_KEY")

# Normal Forex pairs
PAIRS = {
    "EURUSD": ("EUR", "USD"),
    "GBPUSD": ("GBP", "USD"),
    "USDJPY": ("USD", "JPY"),
    "AUDUSD": ("AUD", "USD"),
    "USDCAD": ("USD", "CAD"),
    "EURJPY": ("EUR", "JPY"),
    "GBPJPY": ("GBP", "JPY"),
}


@app.get("/")
def home():
    return {
        "status": "online",
        "message": "Live Forex Signal Backend Running",
        "market": "FOREX",
        "timeframe": "M1",
        "api_configured": bool(API_KEY),
        "pairs": list(PAIRS.keys())
    }


@app.get("/api/v1/status")
def status():
    return {
        "status": "online",
        "market": "FOREX",
        "timeframe": "M1",
        "api_configured": bool(API_KEY),
        "pairs": list(PAIRS.keys())
    }


def get_signal(closes):
    if len(closes) < 6:
        return "WAIT", 0

    recent = closes[-6:]

    up = 0
    down = 0

    for i in range(1, len(recent)):
        if recent[i] > recent[i - 1]:
            up += 1
        elif recent[i] < recent[i - 1]:
            down += 1

    if up >= 4 and up > down:
        strength = min(95, 60 + up * 7)
        return "BUY", strength

    if down >= 4 and down > up:
        strength = min(95, 60 + down * 7)
        return "SELL", strength

    return "WAIT", 0


@app.get("/api/v1/candles")
def candles(symbol: str = "EURUSD"):

    if not API_KEY:
        return {
            "status": "error",
            "market": "FOREX",
            "symbol": symbol,
            "timeframe": "M1",
            "signal": "WAIT",
            "strength": 0,
            "price": None,
            "error": "API_KEY_NOT_CONFIGURED"
        }

    if symbol not in PAIRS:
        return {
            "status": "error",
            "market": "FOREX",
            "symbol": symbol,
            "timeframe": "M1",
            "signal": "WAIT",
            "strength": 0,
            "price": None,
            "error": "UNSUPPORTED_SYMBOL",
            "available_pairs": list(PAIRS.keys())
        }

    from_currency, to_currency = PAIRS[symbol]

    url = "https://www.alphavantage.co/query"

    params = {
        "function": "FX_INTRADAY",
        "from_symbol": from_currency,
        "to_symbol": to_currency,
        "interval": "1min",
        "outputsize": "compact",
        "apikey": API_KEY
    }

    try:
        response = requests.get(
            url,
            params=params,
            timeout=20
        )

        response.raise_for_status()

        data = response.json()

        # Alpha Vantage errors
        if "Error Message" in data:
            return {
                "status": "error",
                "market": "FOREX",
                "symbol": symbol,
                "timeframe": "M1",
                "signal": "WAIT",
                "strength": 0,
                "price": None,
                "error": "ALPHAVANTAGE_ERROR",
                "message": data["Error Message"]
            }

        if "Note" in data:
            return {
                "status": "error",
                "market": "FOREX",
                "symbol": symbol,
                "timeframe": "M1",
                "signal": "WAIT",
                "strength": 0,
                "price": None,
                "error": "API_LIMIT",
                "message": data["Note"]
            }

        time_series = None

        for key in data.keys():
            if key.startswith("Time Series FX"):
                time_series = data[key]
                break

        if not time_series:
            return {
                "status": "error",
                "market": "FOREX",
                "symbol": symbol,
                "timeframe": "M1",
                "signal": "WAIT",
                "strength": 0,
                "price": None,
                "error": "NO_CANDLE_DATA",
                "message": "No 1-minute candle data returned"
            }

        sorted_times = sorted(
            time_series.keys()
        )

        recent_times = sorted_times[-10:]

        closes = []

        for t in recent_times:
            candle = time_series[t]

            close_value = (
                candle.get("4. close")
                or candle.get("close")
            )

            if close_value is not None:
                closes.append(float(close_value))

        if len(closes) < 6:
            return {
                "status": "error",
                "market": "FOREX",
                "symbol": symbol,
                "timeframe": "M1",
                "signal": "WAIT",
                "strength": 0,
                "price": closes[-1] if closes else None,
                "error": "NOT_ENOUGH_CANDLES"
            }

        price = closes[-1]

        signal, strength = get_signal(closes)

        return {
            "status": "online",
            "market": "FOREX",
            "symbol": symbol,
            "timeframe": "M1",
            "signal": signal,
            "strength": strength,
            "price": price,
            "candleTime": recent_times[-1],
            "source": "Alpha Vantage",
            "serverTime": datetime.now(
                timezone.utc
            ).isoformat()
        }

    except requests.RequestException as e:

        return {
            "status": "error",
            "market": "FOREX",
            "symbol": symbol,
            "timeframe": "M1",
            "signal": "WAIT",
            "strength": 0,
            "price": None,
            "error": "API_REQUEST_FAILED",
            "message": str(e)
        }

    except Exception as e:

        return {
            "status": "error",
            "market": "FOREX",
            "symbol": symbol,
            "timeframe": "M1",
            "signal": "WAIT",
            "strength": 0,
            "price": None,
            "error": "SERVER_ERROR",
            "message": str(e)
        }
