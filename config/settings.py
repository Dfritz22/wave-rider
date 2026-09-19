"""Central configuration for wave-rider. Non-secret tunables only.

Secrets (API keys, Telegram token) come from the environment / .env and are
read here via os.getenv — never hard-code them. See DESIGN.md sections 4-5 for
the meaning of each detector parameter.
"""
from __future__ import annotations

import os
from datetime import time
from zoneinfo import ZoneInfo

from config import calibration as _calibration

# --- Timezone ---
MARKET_TZ = ZoneInfo("America/New_York")

# --- Calibration knobs (editable JSON; see config/calibration.py) ---
_CAL = _calibration.load()

# --- Secrets / environment (loaded from .env on the droplet) ---
ALPACA_API_KEY = os.getenv("ALPACA_API_KEY", "")
ALPACA_SECRET_KEY = os.getenv("ALPACA_SECRET_KEY", "")
ALPACA_DATA_URL = os.getenv("ALPACA_DATA_URL", "https://data.alpaca.markets")
ALPACA_FEED = os.getenv("ALPACA_FEED", "iex")  # free tier == iex

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# --- Instrument ---
SYMBOL = _CAL["symbol"]

# --- Run mode: "observe" (log only) or "alert" (log + Telegram) ---
MODE = os.getenv("WAVE_RIDER_MODE", "observe").strip().lower()

# --- Session windows (ET) ---
MARKET_OPEN = time(9, 30)
MARKET_CLOSE = time(16, 0)
ACTIVE_WINDOW_START = _calibration.as_time(_CAL["active_window_start"])
ACTIVE_WINDOW_END = _calibration.as_time(_CAL["active_window_end"])
# Baseline "normal minute" is computed from bars in [BASELINE_START, window start).
BASELINE_START = _calibration.as_time(_CAL["baseline_start"])

# --- Detector weights & thresholds (calibrate via config/calibration.json) ---
VELOCITY_WEIGHT = _CAL["velocity_weight"]
RANGE_WEIGHT = _CAL["range_weight"]
PERSISTENCE_WEIGHT = _CAL["persistence_weight"]
VOLUME_WEIGHT = _CAL["volume_weight"]

PERSISTENCE_CAP = _CAL["persistence_cap"]      # bars; caps the persistence component
TRIGGER_SCORE = _CAL["trigger_score"]          # minute score that fires an alert
ALERT_COOLDOWN_MIN = _CAL["alert_cooldown_min"]  # minutes between alerts
ONE_ALERT_PER_SESSION = _CAL["one_alert_per_session"]

# --- Floors to avoid divide-by-zero on flat baselines (dollars / shares) ---
MIN_BASELINE_MOVE = _CAL["min_baseline_move"]
MIN_BASELINE_RANGE = _CAL["min_baseline_range"]
MIN_BASELINE_VOLUME = _CAL["min_baseline_volume"]

# --- Loop timing (seconds) ---
POLL_INTERVAL_SEC = 15       # how often to check for a newly closed bar
IDLE_SLEEP_SEC = 30          # granularity while waiting for the window to open

# --- Storage ---
DATA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "data", "observations"
)

# --- Notifications ---
SEND_STARTUP_HEARTBEAT = True
SEND_DAILY_SUMMARY = True

# --- Execution (Phase 4; keep OFF) ---
AUTOMATE_TRADES = False
