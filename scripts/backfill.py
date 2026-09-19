"""Backfill: score many past sessions to calibrate TRIGGER_SCORE.

Runs the detector across the active window for each weekday in the lookback
range, writes per-day observation logs (like live), and prints a compact
summary: peak score and how many bars would cross candidate thresholds.

Usage:
    python scripts/backfill.py            # last 15 calendar days
    python scripts/backfill.py 30         # last 30 calendar days
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

CANDIDATES = (2.0, 3.0, 4.0)


def at(day, clock):
    return datetime(day.year, day.month, day.day, clock.hour, clock.minute, tzinfo=settings.MARKET_TZ)


def score_day(day, engine, observer):
    df_base = get_minute_bars(at(day, settings.BASELINE_START), at(day, settings.ACTIVE_WINDOW_START))
    window_start = at(day, settings.ACTIVE_WINDOW_START)
    window_end = at(day, settings.ACTIVE_WINDOW_END)
    df_win = get_minute_bars(window_start, window_end)
    df_win = df_win[(df_win.index >= window_start) & (df_win.index <= window_end)]
    if df_win.empty:
        return None
    baseline = engine.compute_baseline(df_base)
    results = [engine.score_latest(df_win.iloc[: i + 1], baseline) for i in range(len(df_win))]
    for r in results:
        observer.record(r)
    return results


def main():
    days_back = int(sys.argv[1]) if len(sys.argv) > 1 else 15
    today = datetime.now(tz=settings.MARKET_TZ).date()
    engine = ImbalanceEngine()
    observer = Observer()

    header = f"{'date':>10}  {'bars':>4}  {'peak':>6}  {'time':>5}  {'dir':>4}  " + \
             "  ".join(f">={c:g}" for c in CANDIDATES)
    print(header)
    print("-" * len(header))

    totals = {c: 0 for c in CANDIDATES}
    days_with_data = 0
    for offset in range(days_back, 0, -1):
        day = today - timedelta(days=offset)
        if day.weekday() >= 5:
            continue
        try:
            results = score_day(day, engine, observer)
        except Exception as exc:
            print(f"{day!s:>10}  error: {exc}")
            continue
        if not results:
            continue
        days_with_data += 1
        peak = max(results, key=lambda r: r.score)
        counts = {c: sum(1 for r in results if r.score >= c) for c in CANDIDATES}
        for c in CANDIDATES:
            totals[c] += counts[c]
        print(f"{day!s:>10}  {len(results):>4}  {peak.score:6.2f}  {peak.timestamp:%H:%M}  "
              f"{peak.direction:>4}  " + "  ".join(f"{counts[c]:>{len(f'>={c:g}')}}" for c in CANDIDATES))

    print("-" * len(header))
    print(f"{days_with_data} sessions. Total bars crossing each threshold: " +
          ", ".join(f">={c:g}: {totals[c]}" for c in CANDIDATES))
    if days_with_data:
        print("Avg alerts/day (pre-cooldown): " +
              ", ".join(f">={c:g}: {totals[c]/days_with_data:.1f}" for c in CANDIDATES))


if __name__ == "__main__":
    main()
