from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from youtube_architect.curriculum_gate import choose_canonical_topic
from youtube_architect.dataway_phases import build_discovery_crew, build_research_crew
from youtube_architect.dataway_state import load_state, save_state, state_for_prompt
from youtube_architect.run_contract import new_run_contract

ROOT = Path(__file__).resolve().parents[2]
RUNS_DIR = ROOT / "runs"


def extract_json(text: str) -> dict[str, Any] | None:
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
    for key in ("topics", "sources", "signals", "feedback"):
        incoming = patch.get(key)
        if isinstance(incoming, dict):
            old.setdefault(key, {})
            for item_key, value in incoming.items():
                if isinstance(value, dict) and isinstance(old[key].get(item_key), dict):
                    old[key][item_key].update(value)
                else:
                    old[key][item_key] = value
    for key in ("research_queue", "learning_queue", "content_queue"):
        incoming = patch.get(key)
        if isinstance(incoming, list):
            old[key] = list(dict.fromkeys(old.setdefault(key, []) + incoming))
    if isinstance(patch.get("system_metrics"), dict):
        old.setdefault("system_metrics", {}).update(patch["system_metrics"])
    return old


def run_daily_locked() -> str:
    state = load_state()
    snapshot = state_for_prompt(state)
    contract = new_run_contract()

    print(f"\n=== DATAWAY RUN {contract.run_id} ===")
    print("Phase 1/2: discovery + analyst + curriculum gate")
    discovery = build_discovery_crew(snapshot).kickoff(inputs={"state_snapshot": snapshot})
    discovery_raw = getattr(discovery, "raw", str(discovery))

    locked = choose_canonical_topic(state, discovery_raw)
    locked.run_id = contract.run_id
    contract = locked
    contract_block = contract.prompt_block()

    print("\n=== CURRICULUM LOCK ===")
    print(contract_block)
    print("\nPhase 2/2: research + learning + content + evaluation + state")
    research = build_research_crew(snapshot, contract_block, discovery_raw).kickoff(
        inputs={
            "state_snapshot": snapshot,
            "contract": contract_block,
            "curriculum_gate_output": discovery_raw,
        }
    )
    research_raw = getattr(research, "raw", str(research))

    now = datetime.now(timezone.utc)
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    report_path = RUNS_DIR / f"locked_{now.strftime('%Y-%m-%d_%H%M%S')}.md"
    report_path.write_text(
        "# Dataway Locked Run\n\n"
        + "## Run Contract\n\n```json\n"
        + json.dumps(contract.as_dict(), indent=2)
        + "\n```\n\n## Discovery / Gate\n\n"
        + discovery_raw
        + "\n\n## Locked Pipeline\n\n"
        + research_raw,
        encoding="utf-8",
    )

    patch = extract_json(research_raw)
    if patch:
        state = merge_state(state, patch)
    else:
        state.setdefault("system_metrics", {})["state_parse_failures"] = state.setdefault("system_metrics", {}).get("state_parse_failures", 0) + 1

    state.setdefault("run_history", []).append({
        "timestamp": now.isoformat(),
        "run_id": contract.run_id,
        "candidate_id": contract.candidate_id,
        "candidate_title": contract.candidate_title,
        "curriculum_position": contract.curriculum_position,
        "decision": contract.decision,
        "report": str(report_path.relative_to(ROOT)),
        "state_updated": bool(patch),
    })
    state["run_history"] = state["run_history"][-30:]
    save_state(state)
    return str(report_path)


if __name__ == "__main__":
    print(f"Daily Dataway locked run complete: {run_daily_locked()}")
