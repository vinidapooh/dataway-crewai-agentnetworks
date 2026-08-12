from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

STATE_PATH = Path(__file__).resolve().parents[2] / "knowledge" / "dataway_state.json"

SEED_TOPICS = {
    "why-ai-is-changing-analytics": {
        "title": "Why AI is changing analytics",
        "status": "current",
        "curriculum_position": 1,
        "prerequisites": [],
        "downstream_concepts": ["llms", "ai-assisted-analytics", "agents"],
        "notes": "Opening mental-model lesson; connect familiar analyst workflows to AI-assisted and agentic workflows.",
    },
    "llms": {
        "title": "What is an LLM? Data -> ML -> LLM",
        "status": "planned",
        "curriculum_position": 2,
        "prerequisites": ["why-ai-is-changing-analytics"],
        "downstream_concepts": ["how-llms-process-information", "tokenization", "context"],
    },
    "how-llms-process-information": {
        "title": "How LLMs process information",
        "status": "planned",
        "curriculum_position": 3,
        "prerequisites": ["llms"],
        "downstream_concepts": ["tokenization", "context"],
    },
    "tokenization": {
        "title": "Feed your AI/LLM data with tokens: tokenization",
        "status": "planned",
        "curriculum_position": 4,
        "prerequisites": ["llms", "how-llms-process-information"],
        "downstream_concepts": ["context", "embeddings", "cost-and-context"],
    },
    "context": {
        "title": "Context windows and prompting",
        "status": "planned",
        "curriculum_position": 5,
        "prerequisites": ["tokenization"],
        "downstream_concepts": ["hallucinations", "rag"],
    },
    "hallucinations": {
        "title": "Why hallucinations happen",
        "status": "planned",
        "curriculum_position": 6,
        "prerequisites": ["llms", "tokenization", "context"],
        "downstream_concepts": ["embeddings", "rag", "evaluation"],
    },
    "embeddings": {
        "title": "Embeddings and semantic meaning",
        "status": "planned",
        "curriculum_position": 7,
        "prerequisites": ["llms", "tokenization"],
        "downstream_concepts": ["vector-databases", "rag"],
    },
    "vector-databases": {
        "title": "Vector databases vs standard databases",
        "status": "planned",
        "curriculum_position": 8,
        "prerequisites": ["embeddings"],
        "downstream_concepts": ["rag", "semantic-search"],
    },
    "rag": {
        "title": "Retrieval-augmented generation (RAG)",
        "status": "planned",
        "curriculum_position": 9,
        "prerequisites": ["embeddings", "vector-databases", "context"],
        "downstream_concepts": ["agents", "enterprise-ai"],
    },
    "agents": {
        "title": "Agents",
        "status": "planned",
        "curriculum_position": 10,
        "prerequisites": ["llms", "context", "rag"],
        "downstream_concepts": ["tool-calling", "mcp", "agentic-analytics"],
    },
    "tool-calling": {
        "title": "Tools and tool calling",
        "status": "planned",
        "curriculum_position": 11,
        "prerequisites": ["agents"],
        "downstream_concepts": ["mcp", "agentic-workflows"],
    },
    "mcp": {
        "title": "Model Context Protocol (MCP)",
        "status": "planned",
        "curriculum_position": 12,
        "prerequisites": ["agents", "tool-calling"],
        "downstream_concepts": ["agentic-analytics", "enterprise-ai"],
    },
    "evaluation-guardrails": {
        "title": "Evaluation and guardrails",
        "status": "planned",
        "curriculum_position": 13,
        "prerequisites": ["llms", "rag", "agents"],
        "downstream_concepts": ["ai-native-analytics", "responsible-ai"],
    },
    "ai-native-analytics": {
        "title": "AI-native analytics and enterprise workflows",
        "status": "planned",
        "curriculum_position": 14,
        "prerequisites": ["rag", "agents", "evaluation-guardrails"],
        "downstream_concepts": [],
    },
}


def _seed_state(state: dict[str, Any]) -> dict[str, Any]:
    topics = state.setdefault("topics", {})
    for topic_id, record in SEED_TOPICS.items():
        existing = topics.get(topic_id, {})
        topics[topic_id] = {**record, **existing}
    state.setdefault("signals", {})
    state.setdefault("sources", {})
    state.setdefault("research_queue", [])
    state.setdefault("learning_queue", [])
    state.setdefault("content_queue", [])
    state.setdefault("feedback", {})
    state.setdefault("system_metrics", {})
    return state


def load_state() -> dict[str, Any]:
    if not STATE_PATH.exists():
        return _seed_state({"version": 2, "last_run": None})
    return _seed_state(json.loads(STATE_PATH.read_text(encoding="utf-8")))


def save_state(state: dict[str, Any]) -> None:
    state["version"] = max(int(state.get("version", 1)), 2)
    state["last_run"] = datetime.now(timezone.utc).isoformat()
    STATE_PATH.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")


def state_for_prompt(state: dict[str, Any]) -> str:
    compact = {
        "version": state.get("version"),
        "last_run": state.get("last_run"),
        "topics": state.get("topics", {}),
        "signals": state.get("signals", {}),
        "sources": state.get("sources", {}),
        "research_queue": state.get("research_queue", []),
        "learning_queue": state.get("learning_queue", []),
        "content_queue": state.get("content_queue", []),
        "feedback": state.get("feedback", {}),
        "system_metrics": state.get("system_metrics", {}),
    }
    return json.dumps(compact, indent=2, ensure_ascii=False)
