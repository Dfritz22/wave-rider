"""Calibration parameters for the detector, stored in an editable JSON file.

These are the knobs you tune while calibrating (and, eventually, from a phone
or web UI): the alert threshold, scoring weights, session windows, cooldown and
baseline floors. They live in ``config/calibration.json`` so they can be changed
without editing Python. Secrets stay in ``.env``; operational constants stay in
``settings.py``.

Use :func:`load` to read the merged, validated values and :func:`save` to write
them back (a future UI writes through the same function so validation is shared).
"""
from __future__ import annotations

import json
import os
from datetime import time

CALIBRATION_PATH = os.path.join(os.path.dirname(__file__), "calibration.json")

# Defaults are the source of truth for the schema. Any key missing from the
# JSON file falls back to the value here, so old files keep working when we add
# new knobs. Times are "HH:MM" strings for easy editing.
DEFAULTS: dict = {
    "symbol": "SPY",
    "active_window_start": "15:45",
    "active_window_end": "16:00",
    "baseline_start": "10:00",
    "velocity_weight": 0.5,
    "range_weight": 0.2,
    "persistence_weight": 0.2,
    "volume_weight": 0.1,
    "persistence_cap": 3,
    "trigger_score": 3.0,
    "alert_cooldown_min": 5,
    "one_alert_per_session": False,
    "min_baseline_move": 0.02,
    "min_baseline_range": 0.03,
    "min_baseline_volume": 1.0,
}

_TIME_KEYS = ("active_window_start", "active_window_end", "baseline_start")
_POSITIVE_NUM_KEYS = (
    "velocity_weight", "range_weight", "persistence_weight", "volume_weight",
    "persistence_cap", "trigger_score", "alert_cooldown_min",
    "min_baseline_move", "min_baseline_range", "min_baseline_volume",
)


class CalibrationError(ValueError):
    """Raised when a calibration file contains invalid values."""


def as_time(hhmm: str) -> time:
    """Parse an "HH:MM" string into a ``datetime.time``."""
    hours, minutes = hhmm.split(":")
    return time(int(hours), int(minutes))


def _validate(values: dict) -> dict:
    for key in _TIME_KEYS:
        try:
            as_time(values[key])
        except (ValueError, AttributeError) as exc:
            raise CalibrationError(f"{key!r} must be 'HH:MM', got {values[key]!r}") from exc
    for key in _POSITIVE_NUM_KEYS:
        val = values[key]
        if not isinstance(val, (int, float)) or isinstance(val, bool) or val < 0:
            raise CalibrationError(f"{key!r} must be a non-negative number, got {val!r}")
    if not isinstance(values["one_alert_per_session"], bool):
        raise CalibrationError("'one_alert_per_session' must be true/false")
    if not str(values["symbol"]).strip():
        raise CalibrationError("'symbol' must be a non-empty string")
    return values


def load(path: str = CALIBRATION_PATH) -> dict:
    """Return calibration values merged over :data:`DEFAULTS` and validated.

    If the file is missing it is created with the defaults so there is always a
    concrete file to edit.
    """
    if not os.path.exists(path):
        save(DEFAULTS, path)
        return dict(DEFAULTS)
    with open(path, "r", encoding="utf-8") as fh:
        stored = json.load(fh)
    merged = {**DEFAULTS, **stored}
    return _validate(merged)


def save(values: dict, path: str = CALIBRATION_PATH) -> dict:
    """Validate and write calibration values to ``path`` (pretty JSON)."""
    merged = _validate({**DEFAULTS, **values})
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(merged, fh, indent=2)
        fh.write("\n")
    return merged
