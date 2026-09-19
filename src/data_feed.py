"""Alpaca (IEX free tier) 1-minute bar retrieval with retry/backoff.

Returns tz-aware (ET) OHLCV DataFrames. Network errors are retried with
exponential backoff and surfaced as DataFeedError so the caller can keep the
daemon alive (see main.py).
"""
from __future__ import annotations

import time as _time
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
import requests

from config import settings

UTC = ZoneInfo("UTC")
_COLUMNS = ["open", "high", "low", "close", "volume"]


class DataFeedError(Exception):
    """Raised when bar data cannot be retrieved after retries."""


def empty_bars() -> pd.DataFrame:
    """An empty OHLCV frame with the standard columns/index name."""
    df = pd.DataFrame(columns=_COLUMNS)
    df.index.name = "timestamp"
    return df


def _headers() -> dict:
    return {
        "APCA-API-KEY-ID": settings.ALPACA_API_KEY,
        "APCA-API-SECRET-KEY": settings.ALPACA_SECRET_KEY,
    }


def _rfc3339(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=settings.MARKET_TZ)
    return dt.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def get_minute_bars(
    start: datetime,
    end: datetime,
    symbol: str | None = None,
    max_retries: int = 4,
) -> pd.DataFrame:
    """Return 1-minute bars for [start, end] as a tz-aware (ET) DataFrame.

    Columns: open, high, low, close, volume. Empty frame if the API has no data.
    """
    symbol = symbol or settings.SYMBOL
    if not (settings.ALPACA_API_KEY and settings.ALPACA_SECRET_KEY):
        raise DataFeedError("Alpaca API credentials are not set (check .env).")

    url = f"{settings.ALPACA_DATA_URL}/v2/stocks/{symbol}/bars"
    base_params = {
        "timeframe": "1Min",
        "start": _rfc3339(start),
        "end": _rfc3339(end),
        "feed": settings.ALPACA_FEED,
        "adjustment": "raw",
        "limit": 10000,
    }

    rows: list[dict] = []
    page_token: str | None = None
    while True:
        params = dict(base_params)
        if page_token:
            params["page_token"] = page_token
        data = _request_with_retry(url, params, max_retries)
        rows.extend(data.get("bars") or [])
        page_token = data.get("next_page_token")
        if not page_token:
            break

    if not rows:
        return empty_bars()

    df = pd.DataFrame(rows)
    df["timestamp"] = pd.to_datetime(df["t"], utc=True).dt.tz_convert(settings.MARKET_TZ)
    df = df.rename(columns={"o": "open", "h": "high", "l": "low", "c": "close", "v": "volume"})
    return df.set_index("timestamp")[_COLUMNS].astype(float)


def _request_with_retry(url: str, params: dict, max_retries: int) -> dict:
    delay = 1.0
    last_err = "unknown error"
    for attempt in range(1, max_retries + 1):
        try:
            resp = requests.get(url, headers=_headers(), params=params, timeout=15)
            if resp.status_code == 200:
                return resp.json()
            if resp.status_code == 429:
                last_err = "rate limited (429)"
            else:
                last_err = f"HTTP {resp.status_code}: {resp.text[:200]}"
        except requests.RequestException as exc:
            last_err = str(exc)
        _time.sleep(delay)
        delay *= 2
    raise DataFeedError(f"bar request failed after {max_retries} attempts: {last_err}")
