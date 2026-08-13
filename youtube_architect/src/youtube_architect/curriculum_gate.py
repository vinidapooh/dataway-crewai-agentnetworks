from __future__ import annotations

import json
import re
from typing import Any

from youtube_architect.run_contract import RunContract


def _normalise(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def choose_canonical_topic(state: dict[str, Any], curriculum_output: str) -> RunContract:
    """Convert the curriculum gate's prose into one explicit canonical topic lock."""
    topics = state.get("topics", {})
    text = curriculum_output.strip()

    # Prefer a JSON object when the gate follows the requested structure.
    candidates: list[dict[str, Any]] = []
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            candidates = parsed.get("research_now", []) or parsed.get("selected_topics", []) or []
            if isinstance(candidates, dict):
                candidates = [candidates]
    except json.JSONDecodeError:
        pass

    # First try explicit topic IDs/names from structured output.
    for item in candidates:
        if not isinstance(item, dict):
            continue
        topic_id = item.get("topic_id") or item.get("curriculum_topic_id") or item.get("id")
        if topic_id in topics:
            record = topics[topic_id]
            contract = RunContract(run_id="pending")
            contract.lock_candidate(
                candidate_id=topic_id,
                candidate_title=item.get("title") or record.get("title", topic_id),
                curriculum_topic_id=topic_id,
                curriculum_title=record.get("title", topic_id),
                curriculum_position=str(record.get("curriculum_position", "")),
                decision="research-now",
            )
            return contract

    # Fallback: match a known curriculum title mentioned by the gate.
    normalised_text = _normalise(text)
    matches: list[tuple[int, str]] = []
    for topic_id, record in topics.items():
        title = str(record.get("title", ""))
        if not title:
            continue
        title_norm = _normalise(title)
        if title_norm and title_norm in normalised_text:
            matches.append((int(record.get("curriculum_position", 999)), topic_id))

    if matches:
        _, topic_id = sorted(matches)[0]
        record = topics[topic_id]
        contract = RunContract(run_id="pending")
        contract.lock_candidate(
            candidate_id=topic_id,
            candidate_title=record.get("title", topic_id),
            curriculum_topic_id=topic_id,
            curriculum_title=record.get("title", topic_id),
            curriculum_position=str(record.get("curriculum_position", "")),
            decision="research-now",
        )
        return contract

    raise ValueError("Curriculum gate did not identify a canonical Dataway topic.")
