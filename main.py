"""wave-rider — late-day SPY MOC-imbalance detector & notifier.

v1 is alert-only (no trading). Runs a continuous market-hours loop:
  1. Wait for the active window (15:45-16:00 ET).
  2. Build a per-session baseline from earlier bars.
  3. Score each new closed 1-minute bar; log it (Phase 0).
  4. In "alert" mode, ping Telegram when the score triggers.

See DESIGN.md for the full plan. Weekends are skipped; market holidays are a
known open item (see DESIGN.md section 9).
"""
from __future__ import annotations

import time as _time
from datetime import datetime, time as dtime, timedelta

from dotenv import load_dotenv

load_dotenv()  # populate env from .env before settings reads os.getenv

from config import settings  # noqa: E402
from src.alert_dispatcher import TelegramDispatcher  # noqa: E402
from src.data_feed import DataFeedError, empty_bars, get_minute_bars  # noqa: E402
from src.execution_manager import ExecutionManager  # noqa: E402
from src.imbalance_engine import ImbalanceEngine  # noqa: E402
from src.observer import Observer  # noqa: E402


def now_et() -> datetime:
    return datetime.now(tz=settings.MARKET_TZ)


def is_trading_day(moment: datetime) -> bool:
    return moment.weekday() < 5  # Mon-Fri; holidays not handled (see DESIGN.md)


def at(day: datetime, clock: dtime) -> datetime:
    return day.replace(hour=clock.hour, minute=clock.minute, second=0, microsecond=0)


def run_session(engine: ImbalanceEngine, observer: Observer,
                dispatcher: TelegramDispatcher, execmgr: ExecutionManager) -> None:
    today = now_et()
    window_start = at(today, settings.ACTIVE_WINDOW_START)
    window_end = at(today, settings.ACTIVE_WINDOW_END)
    baseline_start = at(today, settings.BASELINE_START)

    while now_et() < window_start:
        _time.sleep(settings.IDLE_SLEEP_SEC)

    dispatcher.reset_session()

    try:
        df_base = get_minute_bars(baseline_start, window_start)
    except DataFeedError as exc:
        print(f"[main] baseline fetch failed: {exc}; using floor baseline")
        df_base = empty_bars()
    baseline = engine.compute_baseline(df_base)
    print(f"[main] baseline move={baseline.move:.3f} "
          f"range={baseline.range:.3f} vol={baseline.volume:.0f}")

    seen: set = set()
    while now_et() <= window_end + timedelta(seconds=5):
        try:
            df = get_minute_bars(window_start, now_et())
        except DataFeedError as exc:
            print(f"[main] bar fetch error: {exc}")
            _time.sleep(settings.POLL_INTERVAL_SEC)
            continue

        if not df.empty and df.index[-1] not in seen:
            seen.add(df.index[-1])
            result = engine.score_latest(df, baseline)
            if result is not None:
                observer.record(result)
                print(f"[{result.timestamp:%H:%M}] score={result.score:.2f} "
                      f"dir={result.direction} vel={result.velocity_norm:.1f} "
                      f"rng={result.range_norm:.1f} vol={result.volume_norm:.1f} "
                      f"drive={result.persistence} trig={result.triggered}")
                if settings.MODE == "alert" and result.triggered:
                    if dispatcher.maybe_alert_signal(result):
                        execmgr.handle_signal(result)

        _time.sleep(settings.POLL_INTERVAL_SEC)

    if settings.SEND_DAILY_SUMMARY and settings.MODE == "alert":
        dispatcher.notify(
            f"wave-rider: session complete {today:%Y-%m-%d}. Bars observed: {len(seen)}."
        )


def main() -> None:
    print(f"[main] wave-rider starting in {settings.MODE.upper()} mode for {settings.SYMBOL}")
    engine = ImbalanceEngine()
    observer = Observer()
    dispatcher = TelegramDispatcher()
    execmgr = ExecutionManager()

    if settings.SEND_STARTUP_HEARTBEAT and settings.MODE == "alert":
        dispatcher.notify(
            f"wave-rider online ({settings.MODE} mode). Watching {settings.SYMBOL} "
            f"{settings.ACTIVE_WINDOW_START:%H:%M}-{settings.ACTIVE_WINDOW_END:%H:%M} ET."
        )

    while True:
        try:
            today = now_et()
            if not is_trading_day(today):
                _time.sleep(3600)
                continue
            if now_et() > at(today, settings.ACTIVE_WINDOW_END):
                _time.sleep(1800)  # past today's window; wait for the next day
                continue
            run_session(engine, observer, dispatcher, execmgr)
            _time.sleep(1800)  # roll past the window before re-evaluating
        except KeyboardInterrupt:
            print("[main] shutting down.")
            break
        except Exception as exc:  # keep the daemon alive across unexpected errors
            print(f"[main] unexpected error: {exc}")
            _time.sleep(60)


if __name__ == "__main__":
    main()
