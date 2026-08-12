from __future__ import annotations

import json
from pathlib import Path
from typing import Any


STATE_PATH = Path(__file__).resolve().parents[2] / "state" / "dataway_state.json"

DEFAULT_STATE: dict[str, Any] = {
    "version": 1,
    "last_run": None,
    "topics": {},
    "sources": {},
    "signals": [],
    "feedback": [],
}


def load_state() -> dict[str, Any]:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not STATE_PATH.exists():
        return json.loads(json.dumps(DEFAULT_STATE))
    try:
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return json.loads(json.dumps(DEFAULT_STATE))


def save_state(state: dict[str, Any]) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = STATE_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(STATE_PATH)


def merge_daily_result(state: dict[str, Any], result: dict[str, Any], run_date: str) -> None:
    state["last_run"] = run_date

    for topic in result.get("topics", []):
        key = topic.get("id") or topic.get("name", "").strip().lower().replace(" ", "_")
        if not key:
            continue
        existing = state["topics"].get(key, {})
        existing.update(topic)
        existing["last_seen"] = run_date
        existing["status"] = existing.get("status", "candidate")
        state["topics"][key] = existing

    for source in result.get("sources", []):
        url = source.get("url", "").strip()
        if not url:
            continue
        existing = state["sources"].get(url, {})
        existing.update(source)
        existing["last_seen"] = run_date
        state["sources"][url] = existing

    for signal in result.get("signals", []):
        state["signals"].append({**signal, "seen_on": run_date})

    # Keep the repository state intentionally small. Detailed reports live in outputs/.
    state["signals"] = state["signals"][-250:]
    state["feedback"] = state.get("feedback", [])[-100:]
