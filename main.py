from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os
import time

app = FastAPI(title="Quotex OTC Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def home():
    return {
        "status": "online",
        "message": "Quotex OTC Backend Running",
        "market": "QUOTEX_OTC",
        "timeframe": "M1",
        "connection": "NOT_CONNECTED"
    }


@app.get("/api/v1/status")
def status():
    return {
        "status": "online",
        "market": "QUOTEX_OTC",
        "timeframe": "M1",
        "quotex_access": "BLOCKED_403",
        "message": "Quotex server rejected the server-side connection."
    }


@app.get("/api/v1/candles")
def candles(symbol: str = "EURUSD_otc"):

    return {
        "status": "error",
        "market": "QUOTEX_OTC",
        "symbol": symbol,
        "timeframe": "M1",
        "error": "QUOTEX_ACCESS_BLOCKED",
        "http_status": 403,
        "message": (
            "Quotex rejected the server-side request. "
            "No fake candles are generated."
        ),
        "candles": []
    }
