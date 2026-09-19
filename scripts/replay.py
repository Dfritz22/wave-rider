"""Replay a past session's active window through the detector (no live wait).

Feeds each 1-minute bar in the active window to the engine incrementally, so
persistence and scoring behave exactly as they would live. Writes to
data/observations/ like the live loop. Doubles as the Phase 0 calibration tool.

Usage:
    python scripts/replay.py            # most recent weekday
    python scripts/replay.py 2026-09-18 # a specific date (YYYY-MM-DD)
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv()

from config import settings  # noqa: E402
from src.data_feed import get_minute_bars  # noqa: E402
from src.imbalance_engine import ImbalanceEngine  # noqa: E402
from src.observer import Observer  # noqa: E402


def resolve_day(arg: str | None):
    if arg:
        return datetime.strptime(arg, "%Y-%m-%d").date()
    day = datetime.now(tz=settings.MARKET_TZ).date()
    while day.weekday() >= 5:  # roll back off the weekend
        day -= timedelta(days=1)
    return day


def at(day, clock):
    return datetime(day.year, day.month, day.day, clock.hour, clock.minute, tzinfo=settings.MARKET_TZ)


def main():
    day = resolve_day(sys.argv[1] if len(sys.argv) > 1 else None)
    baseline_start = at(day, settings.BASELINE_START)
    window_start = at(day, settings.ACTIVE_WINDOW_START)
    window_end = at(day, settings.ACTIVE_WINDOW_END)

    print(f"Replaying {day} active window "
          f"{settings.ACTIVE_WINDOW_START:%H:%M}-{settings.ACTIVE_WINDOW_END:%H:%M} ET\n")

    engine = ImbalanceEngine()
    observer = Observer()

    df_base = get_minute_bars(baseline_start, window_start)
    baseline = engine.compute_baseline(df_base)
    print(f"baseline: move={baseline.move:.3f}  range={baseline.range:.3f}  "
          f"vol={baseline.volume:.0f}  (from {len(df_base)} bars)\n")

    df_win = get_minute_bars(window_start, window_end)
    df_win = df_win[(df_win.index >= window_start) & (df_win.index <= window_end)]
    if df_win.empty:
        print("No bars in the active window.")
        return

    print(f"{'time':>5}  {'score':>6}  {'dir':>4}  {'vel':>5}  {'rng':>5}  {'vol':>6}  {'drive':>5}  trig")
    peak = None
    for i in range(len(df_win)):
        result = engine.score_latest(df_win.iloc[: i + 1], baseline)
        observer.record(result)
        if peak is None or result.score > peak.score:
            peak = result
        print(f"{result.timestamp:%H:%M}  {result.score:6.2f}  {result.direction:>4}  "
              f"{result.velocity_norm:5.1f}  {result.range_norm:5.1f}  {result.volume_norm:6.1f}  "
              f"{result.persistence:>5}  {result.triggered}")

    print(f"\nPeak score {peak.score:.2f} at {peak.timestamp:%H:%M} ({peak.direction}). "
          f"TRIGGER_SCORE={settings.TRIGGER_SCORE}")
    print(f"Logged to data/observations/{day:%Y-%m-%d}.jsonl")


if __name__ == "__main__":
    main()
