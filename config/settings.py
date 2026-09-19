"""Central configuration for wave-rider. Non-secret tunables only.

Secrets (API keys, Telegram token) come from the environment / .env and are
read here via os.getenv — never hard-code them. See DESIGN.md sections 4-5 for
the meaning of each detector parameter.
"""
from __future__ import annotations

import os
from datetime import time
from zoneinfo import ZoneInfo

# --- Timezone ---
MARKET_TZ = ZoneInfo("America/New_York")

# --- Secrets / environment (loaded from .env on the droplet) ---
ALPACA_API_KEY = os.getenv("ALPACA_API_KEY", "")
ALPACA_SECRET_KEY = os.getenv("ALPACA_SECRET_KEY", "")
ALPACA_DATA_URL = os.getenv("ALPACA_DATA_URL", "https://data.alpaca.markets")
ALPACA_FEED = os.getenv("ALPACA_FEED", "iex")  # free tier == iex

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# --- Instrument ---
SYMBOL = "SPY"

# --- Run mode: "observe" (log only) or "alert" (log + Telegram) ---
MODE = os.getenv("WAVE_RIDER_MODE", "observe").strip().lower()

# --- Session windows (ET) ---
MARKET_OPEN = time(9, 30)
MARKET_CLOSE = time(16, 0)
ACTIVE_WINDOW_START = time(15, 45)
ACTIVE_WINDOW_END = time(16, 0)
# Baseline "normal minute" is computed from bars in [BASELINE_START, window start).
BASELINE_START = time(10, 0)

# --- Detector weights & thresholds (provisional; calibrate from Phase 0) ---
VELOCITY_WEIGHT = 0.5
RANGE_WEIGHT = 0.2
PERSISTENCE_WEIGHT = 0.2
VOLUME_WEIGHT = 0.1

PERSISTENCE_CAP = 3          # bars; caps the persistence component
TRIGGER_SCORE = 3.0          # TBD after Phase 0 observation
ALERT_COOLDOWN_MIN = 5       # minutes between alerts (one event => one alert)
ONE_ALERT_PER_SESSION = False

# --- Floors to avoid divide-by-zero on flat baselines (dollars / shares) ---
MIN_BASELINE_MOVE = 0.02
MIN_BASELINE_RANGE = 0.03
MIN_BASELINE_VOLUME = 1.0

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
