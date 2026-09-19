"""Execution router — STUB (alert-only in v1).

AUTOMATE_TRADES is False, so this never places orders. It exists as the single,
clean integration point for Phase 4 opt-in automation (broker / Robinhood MCP
tool calls), guarded there by a hard pre-close exit safeguard. Do not add live
order code until DESIGN.md Phase 4 is explicitly reached.
"""
from __future__ import annotations

from config import settings
from src.imbalance_engine import ScoreResult


class ExecutionManager:
    def __init__(self, cfg=settings):
        self.automate = cfg.AUTOMATE_TRADES

    def handle_signal(self, result: ScoreResult) -> None:
        if not self.automate:
            return  # Alert-only: notifications are handled by the dispatcher.
        # --- Phase 4 placeholder: integrate broker/MCP order placement here,
        # behind a hard pre-close exit safeguard (see DESIGN.md section 6). ---
        raise NotImplementedError("Automated execution is not enabled in v1.")
