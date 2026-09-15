from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime, timezone

app = FastAPI(title="Quotex OTC Live Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Current OTC pairs configured from the screenshot
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
        "message": "Quotex OTC Backend Running",
        "market": "QUOTEX_OTC",
        "timeframe": "M1",
        "connection": "NOT_CONNECTED",
        "pairs": OTC_PAIRS
    }


@app.get("/api/v1/status")
def status():
    return {
        "status": "online",
        "market": "QUOTEX_OTC",
        "timeframe": "M1",
        "connection": "NOT_CONNECTED",
        "quotex_access": "BLOCKED_OR_NOT_CONNECTED",
        "pairs": OTC_PAIRS,
        "message": (
            "Backend is online, but no real Quotex OTC candle "
            "connection is available."
        )
    }


@app.get("/api/v1/pairs")
def pairs():
    return {
        "status": "online",
        "market": "QUOTEX_OTC",
        "timeframe": "M1",
        "pairs": OTC_PAIRS
    }


@app.get("/api/v1/candles")
def candles(symbol: str = "AUDNZD_otc"):

    if symbol not in OTC_PAIRS:
        return {
            "status": "error",
            "market": "QUOTEX_OTC",
            "symbol": symbol,
            "timeframe": "M1",
            "error": "UNSUPPORTED_OTC_PAIR",
            "candles": []
        }

    return {
        "status": "error",
        "market": "QUOTEX_OTC",
        "symbol": symbol,
        "timeframe": "M1",
        "error": "QUOTEX_ACCESS_BLOCKED",
        "http_status": 403,
        "connection": "NOT_CONNECTED",
        "message": (
            "Real Quotex OTC candles are not available. "
            "No fake candles or fake signals are generated."
        ),
        "serverTime": datetime.now(timezone.utc).isoformat(),
        "candles": []
    }
