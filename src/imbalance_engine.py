"""Imbalance detection math.

Builds a per-session baseline of a "normal minute", then scores each closed
1-minute bar in the active window into a single composite number. Price
behaviour (velocity, range, persistence) is weighted ahead of volume because
the free IEX feed under-reports consolidated volume (see DESIGN.md section 5).
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from config import settings


@dataclass
class Baseline:
    move: float    # typical |close-open| per minute (dollars)
    range: float   # typical high-low per minute (dollars)
    volume: float  # typical per-minute volume (shares)


@dataclass
class ScoreResult:
    timestamp: pd.Timestamp
    close: float
    direction: str  # "CALL" | "PUT" | "FLAT"
    velocity_norm: float
    range_norm: float
    persistence: int
    persistence_norm: float
    volume_norm: float
    score: float
    triggered: bool

    def to_record(self) -> dict:
        return {
            "timestamp": self.timestamp.isoformat(),
            "close": round(float(self.close), 4),
            "direction": self.direction,
            "velocity_norm": round(float(self.velocity_norm), 3),
            "range_norm": round(float(self.range_norm), 3),
            "persistence": int(self.persistence),
            "persistence_norm": round(float(self.persistence_norm), 3),
            "volume_norm": round(float(self.volume_norm), 3),
            "score": round(float(self.score), 3),
            "triggered": bool(self.triggered),
        }


def _sign(value: float) -> int:
    return (value > 0) - (value < 0)


class ImbalanceEngine:
    def __init__(self, cfg=settings):
        self.cfg = cfg

    def compute_baseline(self, df_baseline: pd.DataFrame) -> Baseline:
        """Derive the 'normal minute' from earlier-session bars."""
        if df_baseline is None or df_baseline.empty:
            return Baseline(
                self.cfg.MIN_BASELINE_MOVE,
                self.cfg.MIN_BASELINE_RANGE,
                self.cfg.MIN_BASELINE_VOLUME,
            )
        moves = (df_baseline["close"] - df_baseline["open"]).abs()
        ranges = df_baseline["high"] - df_baseline["low"]
        return Baseline(
            move=max(float(moves.median()), self.cfg.MIN_BASELINE_MOVE),
            range=max(float(ranges.mean()), self.cfg.MIN_BASELINE_RANGE),
            volume=max(float(df_baseline["volume"].mean()), self.cfg.MIN_BASELINE_VOLUME),
        )

    def _persistence(self, df_window: pd.DataFrame) -> tuple[int, str]:
        """Count consecutive same-direction bars ending at the latest bar."""
        signs = (df_window["close"] - df_window["open"]).tolist()
        if not signs:
            return 0, "FLAT"
        current = _sign(signs[-1])
        if current == 0:
            return 0, "FLAT"
        count = 0
        for value in reversed(signs):
            if _sign(value) == current:
                count += 1
            else:
                break
        return count, ("CALL" if current > 0 else "PUT")

    def score_latest(self, df_day: pd.DataFrame, baseline: Baseline) -> ScoreResult | None:
        """Score the most recent closed bar in df_day against the baseline."""
        if df_day is None or df_day.empty:
            return None
        bar = df_day.iloc[-1]

        velocity_norm = abs(bar["close"] - bar["open"]) / baseline.move
        range_norm = (bar["high"] - bar["low"]) / baseline.range
        volume_norm = bar["volume"] / baseline.volume
        persistence, direction = self._persistence(df_day)
        persistence_norm = min(persistence, self.cfg.PERSISTENCE_CAP) / self.cfg.PERSISTENCE_CAP

        score = (
            self.cfg.VELOCITY_WEIGHT * velocity_norm
            + self.cfg.RANGE_WEIGHT * range_norm
            + self.cfg.PERSISTENCE_WEIGHT * persistence_norm
            + self.cfg.VOLUME_WEIGHT * volume_norm
        )

        return ScoreResult(
            timestamp=df_day.index[-1],
            close=float(bar["close"]),
            direction=direction,
            velocity_norm=velocity_norm,
            range_norm=range_norm,
            persistence=persistence,
            persistence_norm=persistence_norm,
            volume_norm=volume_norm,
            score=score,
            triggered=score >= self.cfg.TRIGGER_SCORE,
        )
