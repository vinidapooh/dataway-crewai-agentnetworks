from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from youtube_architect.dataway_crew import build_crew
from youtube_architect.dataway_state import load_state, save_state, state_for_prompt

ROOT = Path(__file__).resolve().parents[2]
RUNS_DIR = ROOT / "runs"


def extract_json(text: str) -> dict[str, Any] | None:
    """Extract the final state JSON even if an LLM accidentally adds a fence."""
    text = text.strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.DOTALL)
    candidate = fenced.group(1) if fenced else text
    try:
        value = json.loads(candidate)
        return value if isinstance(value, dict) else None
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}\s*$", text, re.DOTALL)
        if not match:
            return None
        try:
            value = json.loads(match.group(0))
            return value if isinstance(value, dict) else None
        except json.JSONDecodeError:
            return None


def merge_state(old: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    """Conservatively merge agent-generated memory; never replace the whole state."""
    for key in ("topics", "sources", "feedback"):
        incoming = patch.get(key)
        if isinstance(incoming, dict):
            old.setdefault(key, {}).update(incoming)

    for key in ("research_queue", "learning_queue", "content_queue"):
        incoming = patch.get(key)
        if isinstance(incoming, list):
            existing = old.setdefault(key, [])
            old[key] = list(dict.fromkeys(existing + incoming))

    metrics = patch.get("system_metrics")
    if isinstance(metrics, dict):
        old.setdefault("system_metrics", {}).update(metrics)
    return old


def run_daily() -> str:
    state = load_state()
    crew = build_crew(state_for_prompt(state))
    result = crew.kickoff(inputs={"state_snapshot": state_for_prompt(state)})
    raw = getattr(result, "raw", str(result))

    now = datetime.now(timezone.utc)
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    report_path = RUNS_DIR / f"{now.strftime('%Y-%m-%d_%H%M%S')}.md"
    report_path.write_text(raw, encoding="utf-8")

    patch = extract_json(raw)
    if patch:
        state = merge_state(state, patch)
    else:
        state.setdefault("system_metrics", {})["state_parse_failures"] = (
            state.setdefault("system_metrics", {}).get("state_parse_failures", 0) + 1
        )

    state.setdefault("run_history", []).append({
        "timestamp": now.isoformat(),
        "report": str(report_path.relative_to(ROOT)),
        "state_updated": bool(patch),
    })
    state["run_history"] = state["run_history"][-30:]
    save_state(state)
    return str(report_path)


if __name__ == "__main__":
    print(f"Daily Dataway run complete: {run_daily()}")
