from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Any


@dataclass
class RunContract:
    """Identity and curriculum lock carried through one research run."""

    run_id: str
    candidate_id: str | None = None
    candidate_title: str | None = None
    curriculum_topic_id: str | None = None
    curriculum_title: str | None = None
    curriculum_position: str | None = None
    decision: str = "pending"

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)

    def prompt_block(self) -> str:
        values = self.as_dict()
        return "\n".join(f"{key}: {value}" for key, value in values.items())

    def lock_candidate(
        self,
        *,
        candidate_id: str,
        candidate_title: str,
        curriculum_topic_id: str,
        curriculum_title: str,
        curriculum_position: str,
        decision: str,
    ) -> None:
        self.candidate_id = candidate_id
        self.candidate_title = candidate_title
        self.curriculum_topic_id = curriculum_topic_id
        self.curriculum_title = curriculum_title
        self.curriculum_position = curriculum_position
        self.decision = decision


def new_run_contract() -> RunContract:
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return RunContract(run_id=run_id)
