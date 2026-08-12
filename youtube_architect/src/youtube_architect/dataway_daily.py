from __future__ import annotations

import json
import os
from datetime import date
from pathlib import Path

from crewai import Agent, Crew, LLM, Process, Task
from crewai_tools import DuckDuckGoSearchTool
from pydantic import BaseModel, Field

from youtube_architect.dataway_state import load_state, merge_daily_result, save_state


ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIR = ROOT / "outputs"


class Topic(BaseModel):
    id: str
    name: str
    why_now: str
    analyst_relevance: str
    dataway_angle: str
    prerequisites: list[str] = Field(default_factory=list)
    score: float = 0
    status: str = "candidate"


class Source(BaseModel):
    title: str
    url: str
    source_type: str
    topic: str
    why_useful: str


class Signal(BaseModel):
    title: str
    url: str = ""
    signal_type: str
    relevance: str


class DailyResearch(BaseModel):
    topics: list[Topic] = Field(default_factory=list)
    sources: list[Source] = Field(default_factory=list)
    signals: list[Signal] = Field(default_factory=list)
    daily_summary: str
    recommended_next_topics: list[str] = Field(default_factory=list)


def build_llm() -> LLM:
    model = os.getenv("DATAWAY_LLM", "openai/gpt-4o-mini")
    kwargs = {"model": model, "temperature": 0.2}
    if model.startswith("ollama/"):
        kwargs["base_url"] = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    return LLM(**kwargs)


def compact_state(state: dict) -> str:
    topics = list(state.get("topics", {}).values())[-80:]
    sources = list(state.get("sources", {}).values())[-120:]
    return json.dumps({"topics": topics, "sources": sources}, ensure_ascii=False, indent=2)


def run_daily() -> DailyResearch:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    state = load_state()
    today = date.today().isoformat()
    prior_state = compact_state(state)

    search = DuckDuckGoSearchTool()
    llm = build_llm()

    scout = Agent(
        role="Dataway Signal Scout",
        goal=(
            "Discover genuinely useful new signals across AI, agentic AI, analytics, "
            "BI, data engineering, Databricks/Spark and adjacent technology that a "
            "working data professional should understand."
        ),
        backstory=(
            "You are the first filter for Dataway. You are skeptical of hype, prefer "
            "primary or high-quality technical sources, and look for developments "
            "that could change how analysts work. You must search the web rather than "
            "relying on memory."
        ),
        tools=[search],
        llm=llm,
        verbose=True,
    )

    analyst = Agent(
        role="Dataway Analyst Lens",
        goal=(
            "Turn raw technology signals into candidate learning topics for data "
            "professionals, while respecting the Dataway curriculum and teaching philosophy."
        ),
        backstory=(
            "You think like an experienced analyst who knows Excel, SQL, Python, BI "
            "and some data engineering but is learning modern AI. You distinguish "
            "what is technically interesting from what is teachable and useful."
        ),
        llm=llm,
        verbose=True,
    )

    researcher = Agent(
        role="Dataway Source Researcher",
        goal=(
            "Find the strongest sources needed for the most promising candidate topics "
            "and identify what the creator needs to learn before teaching them."
        ),
        backstory=(
            "You are a careful research assistant. You prefer official documentation, "
            "original papers, direct technical explanations and strong educational "
            "material. You never treat a viral post as proof."
        ),
        tools=[search],
        llm=llm,
        verbose=True,
    )

    scout_task = Task(
        description=f"""
Run today's Dataway research scan.

Dataway mission:
{Path(ROOT / 'src/youtube_architect/config/dataway.yaml').read_text(encoding='utf-8')}

Existing state from previous runs:
{prior_state}

Search broadly but prioritize developments from roughly the last 7 days. Look across
AI/LLMs, agentic AI, AI for analytics, BI, data engineering, Databricks/Spark, and
important research or tools. Identify signals that are genuinely new or materially
changed. Avoid repeating topics already present in the existing state unless there is
meaningful new information.

Return a concise research memo containing candidate signals, URLs, and why each could
matter to an analyst. Do not invent URLs.
""",
        expected_output="A concise markdown research memo with signals and source URLs.",
        agent=scout,
    )

    lens_task = Task(
        description=f"""
Using the signal scout memo, evaluate candidate topics against the Dataway mission.

Existing state:
{prior_state}

For each promising topic, determine:
- why it matters now
- analyst relevance
- the Dataway teaching angle
- prerequisites
- whether it belongs in the curriculum now, later, or only on a watchlist
- a 0-10 overall score

Do NOT optimize for generic viral content. Search interest is a signal, not the curriculum.
Prefer concepts that help an analyst understand the modern data stack and that can be
explained with a tabular dataset or paragraph/document.
""",
        expected_output="A ranked list of candidate Dataway topics with reasoning and scores.",
        agent=analyst,
        context=[scout_task],
    )

    research_task = Task(
        description=f"""
Take the ranked candidates from the previous task and research the strongest 3-5 topics.

For each, find high-quality sources that the creator can actually study. Include:
- official documentation where available
- original research/papers when relevant
- one strong explanatory source
- a useful practical/demo source when available

Also identify the concepts the creator must understand before teaching each topic.
Avoid duplicate sources already in the existing state unless they contain meaningful
new information. Do not fabricate URLs.

Existing source registry:
{prior_state}
""",
        expected_output="A source-backed research brief with URLs, topic mapping, and learning prerequisites.",
        agent=researcher,
        context=[scout_task, lens_task],
    )

    synthesis_task = Task(
        description="""
Synthesize the scout, analyst-lens and source-research outputs into the structured
DailyResearch schema.

Rules:
- Include only topics that have enough evidence to be useful.
- Include URLs exactly as discovered; never invent or alter them.
- Keep topics distinct from sources.
- Mark genuinely new topics as candidate; use watchlist only when the evidence is
  interesting but the topic is premature for the Dataway curriculum.
- The daily summary should tell the creator what changed and what deserves attention.
- recommended_next_topics should contain at most 5 topic IDs/names.
""",
        expected_output="A valid DailyResearch object.",
        agent=researcher,
        context=[scout_task, lens_task, research_task],
        output_pydantic=DailyResearch,
    )

    crew = Crew(
        agents=[scout, analyst, researcher],
        tasks=[scout_task, lens_task, research_task, synthesis_task],
        process=Process.sequential,
        verbose=True,
    )

    result = crew.kickoff()
    if not result.pydantic:
        raise RuntimeError("Daily research did not return the expected structured output")

    daily = result.pydantic
    result_dict = daily.model_dump()
    merge_daily_result(state, result_dict, today)
    save_state(state)

    report = f"# Dataway Daily Research — {today}\n\n{daily.daily_summary}\n\n"
    report += "## Recommended topics\n\n"
    for topic in daily.topics:
        report += f"### {topic.name} — {topic.score:.1f}/10\n"
        report += f"**Why now:** {topic.why_now}\n\n"
        report += f"**Analyst relevance:** {topic.analyst_relevance}\n\n"
        report += f"**Dataway angle:** {topic.dataway_angle}\n\n"
        if topic.prerequisites:
            report += "**Prerequisites:** " + ", ".join(topic.prerequisites) + "\n\n"

    report += "## Sources discovered\n\n"
    for source in daily.sources:
        report += f"- **{source.title}** — {source.topic} — {source.source_type}\n  {source.url}\n  {source.why_useful}\n"

    report += "\n## Suggested next topics\n\n"
    for item in daily.recommended_next_topics:
        report += f"- {item}\n"

    (OUTPUT_DIR / f"daily_{today}.md").write_text(report, encoding="utf-8")
    (OUTPUT_DIR / "latest.md").write_text(report, encoding="utf-8")
    return daily


if __name__ == "__main__":
    run_daily()
