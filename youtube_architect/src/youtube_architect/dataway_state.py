from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

STATE_PATH = Path(__file__).resolve().parents[2] / "knowledge" / "dataway_state.json"


def load_state() -> dict[str, Any]:
    if not STATE_PATH.exists():
        return {
            "version": 1,
            "last_run": None,
            "topics": {},
            "sources": {},
            "signals": {},
            "research_queue": [],
            "learning_queue": [],
            "content_queue": [],
            "feedback": {},
            "system_metrics": {},
        }
    return json.loads(STATE_PATH.read_text(encoding="utf-8"))


def save_state(state: dict[str, Any]) -> None:
    state["last_run"] = datetime.now(timezone.utc).isoformat()
    STATE_PATH.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")


def state_for_prompt(state: dict[str, Any]) -> str:
    # Keep the prompt bounded. Full research documents should live in files, not in state.
    compact = {
        "last_run": state.get("last_run"),
        "topics": state.get("topics", {}),
        "sources": state.get("sources", {}),
        "research_queue": state.get("research_queue", []),
        "learning_queue": state.get("learning_queue", []),
        "feedback": state.get("feedback", {}),
        "system_metrics": state.get("system_metrics", {}),
    }
    return json.dumps(compact, indent=2, ensure_ascii=False)
