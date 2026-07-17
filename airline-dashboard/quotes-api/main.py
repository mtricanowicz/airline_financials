"""Live stock quote microservice for the airline dashboard.

A small FastAPI app that returns the most recent daily close for the airline
tickers. Results are cached for the current trading day so the upstream provider
is queried at most once per ticker per day. This service is the only component
that needs live network access at request time; all financial data is precomputed
into static JSON by the core pipeline.
"""

from __future__ import annotations

import datetime as dt
import logging
import os
from threading import Lock

import pandas as pd
import yfinance as yf
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("quotes-api")

DEFAULT_TICKERS = ["AAL", "DAL", "UAL", "LUV", "ALK"]
ALLOWED_ORIGINS = [o for o in os.getenv("ALLOWED_ORIGINS", "*").split(",") if o]

app = FastAPI(title="Airline Dashboard Quotes API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS or ["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

# date -> {ticker: quote}. Reset implicitly when the date key changes.
_cache: dict[dt.date, dict[str, "Quote"]] = {}
_lock = Lock()


class Quote(BaseModel):
    ticker: str
    price: float | None
    change: float | None = None
    change_percent: float | None = None
    as_of: str | None = None
    error: str | None = None


class QuotesResponse(BaseModel):
    quotes: list[Quote]


class History(BaseModel):
    dates: list[str]
    closes: dict[str, list[float | None]]


class HistoryResponse(BaseModel):
    history: History


def _fetch_quote(ticker: str) -> Quote:
    """Fetch the last two daily closes to derive price and day change."""
    try:
        hist = yf.Ticker(ticker).history(period="5d", interval="1d")
        if hist.empty:
            return Quote(ticker=ticker, price=None, error="no data")
        closes = hist["Close"].dropna()
        price = float(closes.iloc[-1])
        prev = float(closes.iloc[-2]) if len(closes) > 1 else price
        change = price - prev
        pct = (change / prev * 100) if prev else 0.0
        as_of = closes.index[-1].date().isoformat()
        return Quote(
            ticker=ticker,
            price=round(price, 2),
            change=round(change, 2),
            change_percent=round(pct, 2),
            as_of=as_of,
        )
    except Exception as exc:  # noqa: BLE001
        log.warning("Quote fetch failed for %s: %s", ticker, exc)
        return Quote(ticker=ticker, price=None, error="fetch failed")


def get_quote_cached(ticker: str) -> Quote:
    today = dt.date.today()
    with _lock:
        day_cache = _cache.setdefault(today, {})
        # Drop stale day buckets to bound memory.
        for key in [k for k in _cache if k != today]:
            _cache.pop(key, None)
        if ticker in day_cache:
            return day_cache[ticker]
    quote = _fetch_quote(ticker)
    # Only cache successful lookups so transient failures can retry.
    if quote.price is not None:
        with _lock:
            _cache.setdefault(today, {})[ticker] = quote
    return quote


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/quotes", response_model=QuotesResponse)
def quotes(
    tickers: str = Query(default=",".join(DEFAULT_TICKERS), description="Comma-separated tickers"),
) -> QuotesResponse:
    symbols = [t.strip().upper() for t in tickers.split(",") if t.strip()]
    return QuotesResponse(quotes=[get_quote_cached(t) for t in symbols])


# (today, start, symbols) -> History payload, so the provider is queried at most
# once per distinct request per trading day. A separate lock serializes the
# actual downloads because yfinance's shared cache is not concurrency-safe.
_history_cache: dict[tuple, History] = {}
_history_fetch_lock = Lock()


def _download_close(sym: str, start: str, attempts: int = 3) -> pd.Series | None:
    """Download one ticker's daily closes, retrying transient provider errors."""
    for attempt in range(attempts):
        try:
            data = yf.download(
                sym, start=start, interval="1d", progress=False, auto_adjust=False
            )
        except Exception as exc:  # noqa: BLE001
            log.warning("History download error for %s (try %d): %s", sym, attempt + 1, exc)
            data = None
        if data is not None and not data.empty:
            close = data["Close"]
            if isinstance(close, pd.DataFrame):
                close = close.iloc[:, 0]
            close = close.dropna()
            if not close.empty:
                return close
    return None


def _fetch_history(symbols: list[str], start: str) -> History:
    """Fetch aligned daily closes for the given tickers since ``start``.

    Each ticker is downloaded on its own so a transient failure or rate-limit on
    one symbol cannot silently drop the others from a batch request.
    """
    frames: dict[str, pd.Series] = {}
    for sym in symbols:
        close = _download_close(sym, start)
        if close is not None:
            frames[sym] = close
    if not frames:
        return History(dates=[], closes={})
    df = pd.DataFrame(frames).sort_index()
    dates = [d.date().isoformat() for d in df.index]
    closes = {
        sym: [None if pd.isna(v) else round(float(v), 4) for v in df[sym]]
        for sym in df.columns
    }
    return History(dates=dates, closes=closes)


@app.get("/history", response_model=HistoryResponse)
def history(
    tickers: str = Query(default=",".join(DEFAULT_TICKERS), description="Comma-separated tickers"),
    start: str = Query(..., description="Start date, YYYY-MM-DD"),
) -> HistoryResponse:
    symbols = [t.strip().upper() for t in tickers.split(",") if t.strip()]
    key = (dt.date.today(), start, tuple(symbols))
    with _lock:
        cached = _history_cache.get(key)
        for stale in [k for k in _history_cache if k[0] != key[0]]:
            _history_cache.pop(stale, None)
    if cached is not None:
        return HistoryResponse(history=cached)

    # Serialize downloads so concurrent identical requests (Streamlit fires
    # several on load) don't hit yfinance's cache at once and lock it.
    with _history_fetch_lock:
        with _lock:
            cached = _history_cache.get(key)
        if cached is not None:
            return HistoryResponse(history=cached)
        try:
            payload = _fetch_history(symbols, start)
        except Exception as exc:  # noqa: BLE001
            log.warning("History fetch failed for %s: %s", symbols, exc)
            payload = History(dates=[], closes={})
        # Only cache once every requested symbol resolved, so a partial provider
        # response is retried rather than served for the rest of the day.
        if payload.dates and all(sym in payload.closes for sym in symbols):
            with _lock:
                _history_cache[key] = payload
    return HistoryResponse(history=payload)
