"""Phase 0 observation logging.

Appends each scored bar to a per-day JSON Lines file so metrics survive
restarts and can be reviewed later to calibrate TRIGGER_SCORE.
"""
from __future__ import annotations

import json
import os

from config import settings
from src.imbalance_engine import ScoreResult


class Observer:
    def __init__(self, data_dir: str | None = None):
        self.data_dir = data_dir or settings.DATA_DIR
        os.makedirs(self.data_dir, exist_ok=True)

    def _path_for(self, timestamp) -> str:
        return os.path.join(self.data_dir, f"{timestamp:%Y-%m-%d}.jsonl")

    def record(self, result: ScoreResult) -> str:
        path = self._path_for(result.timestamp)
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(result.to_record()) + "\n")
        return path
