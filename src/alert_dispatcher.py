"""Telegram notifications with retry and alert cooldown.

Sends plain messages (heartbeat, daily summary) and formatted signal alerts.
Cooldown / one-per-session logic ensures a single imbalance event produces a
single ping rather than a burst.
"""
from __future__ import annotations

import time as _time
from datetime import datetime, timedelta

import requests

from config import settings
from src.imbalance_engine import ScoreResult


class TelegramDispatcher:
    def __init__(self, token: str | None = None, chat_id: str | None = None):
        self.token = token if token is not None else settings.TELEGRAM_BOT_TOKEN
        self.chat_id = chat_id if chat_id is not None else settings.TELEGRAM_CHAT_ID
        self._last_alert_at: datetime | None = None
        self._alerted_this_session = False

    @property
    def configured(self) -> bool:
        return bool(self.token and self.chat_id)

    def notify(self, text: str) -> bool:
        """Send an arbitrary message (heartbeat, summary, etc.)."""
        return self._send(text)

    def maybe_alert_signal(self, result: ScoreResult, now: datetime | None = None) -> bool:
        """Send a signal alert if cooldown / session limits allow."""
        now = now or datetime.now(tz=settings.MARKET_TZ)
        if settings.ONE_ALERT_PER_SESSION and self._alerted_this_session:
            return False
        if self._last_alert_at is not None and (
            now - self._last_alert_at < timedelta(minutes=settings.ALERT_COOLDOWN_MIN)
        ):
            return False
        if self._send(self._format_signal(result)):
            self._last_alert_at = now
            self._alerted_this_session = True
            return True
        return False

    def reset_session(self) -> None:
        self._last_alert_at = None
        self._alerted_this_session = False

    def _send(self, text: str, max_retries: int = 3) -> bool:
        if not self.configured:
            print(f"[alert_dispatcher] Telegram not configured; suppressed: {text}")
            return False
        url = f"https://api.telegram.org/bot{self.token}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }
        delay = 1.0
        for attempt in range(1, max_retries + 1):
            try:
                resp = requests.post(url, json=payload, timeout=10)
                if resp.status_code == 200:
                    return True
                print(f"[alert_dispatcher] HTTP {resp.status_code}: {resp.text[:200]}")
            except requests.RequestException as exc:
                print(f"[alert_dispatcher] send error (attempt {attempt}): {exc}")
            _time.sleep(delay)
            delay *= 2
        return False

    @staticmethod
    def _format_signal(result: ScoreResult) -> str:
        label = {"CALL": "UP (calls)", "PUT": "DOWN (puts)"}.get(result.direction, "FLAT")
        return (
            f"<b>SPY imbalance signal</b>\n"
            f"{label} — score <b>{result.score:.2f}</b>\n"
            f"{result.timestamp:%H:%M} ET   price {result.close:.2f}\n"
            f"vel {result.velocity_norm:.1f}x | rng {result.range_norm:.1f}x | "
            f"vol {result.volume_norm:.1f}x | drive {result.persistence}"
        )
