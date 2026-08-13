from __future__ import annotations

import json
import os
from datetime import date
from pathlib import Path

from crewai import Agent, Crew, LLM, Process, Task
from crewai_tools import DuckDuckGoSearchTool
from pydantic import BaseModel, Field

from youtube_architect.dataway_state import load_state, merge_daily_result, save_state
from youtube_architect.run_contract import RunContract, new_run_contract


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


class CurriculumDecision(BaseModel):
    candidate_id: str
    candidate_title: str
    curriculum_topic_id: str
    curriculum_title: str
    curriculum_position: str
    decision: str
    rationale: str


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


def curriculum_definition() -> str:
    return Path(ROOT / "src/youtube_architect/config/dataway.yaml").read_text(encoding="utf-8")


def run_daily() -> DailyResearch:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    state = load_state()
    today = date.today().isoformat()
    prior_state = compact_state(state)
    contract = new_run_contract()

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
            "relying on memory. A signal is not automatically a curriculum topic."
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
            "what is technically interesting from what is teachable and useful. "
            "You never promote a tool or product into a curriculum topic merely because it is trending."
        ),
        llm=llm,
        verbose=True,
    )

    gate = Agent(
        role="Dataway Curriculum Gate",
        goal=(
            "Select the canonical curriculum subject for this run without allowing "
            "new tools, products or trends to hijack the learning sequence."
        ),
        backstory=(
            "You are the final curriculum authority. The persistent Dataway curriculum "
            "is authoritative. Map interesting signals to existing durable concepts "
            "whenever possible. Create a new branch only when a durable concept cannot "
            "reasonably fit an existing topic. Search trends are packaging signals, not curriculum."
        ),
        llm=llm,
        verbose=True,
    )

    researcher = Agent(
        role="Dataway Source Researcher",
        goal=(
            "Find the strongest sources needed for the locked curriculum topic and "
            "identify what the creator needs to learn before teaching it."
        ),
        backstory=(
            "You are a careful research assistant. You prefer official documentation, "
            "original papers, direct technical explanations and strong educational "
            "material. You never treat a viral post as proof. Once the curriculum "
            "contract is locked, you must not replace the subject with a discovered tool or trend."
        ),
        tools=[search],
        llm=llm,
        verbose=True,
    )

    scout_task = Task(
        description=f"""
Run today's Dataway research scan.

Run ID: {contract.run_id}

Dataway mission:
{curriculum_definition()}

Existing state from previous runs:
{prior_state}

Search broadly but prioritize developments from roughly the last 7 days. Look across
AI/LLMs, agentic AI, AI for analytics, BI, data engineering, Databricks/Spark, and
important research or tools. Identify signals that are genuinely new or materially
changed. Avoid repeating topics already present in the existing state unless there is
meaningful new information.

A discovered signal, company, product, framework or demo is evidence. It is NOT
automatically a Dataway curriculum topic.

Return a concise research memo containing candidate signals, URLs, and why each could
matter to an analyst. Do not invent URLs.
""",
        expected_output="A concise markdown research memo with signals and source URLs.",
        agent=scout,
    )

    lens_task = Task(
        description=f"""
Using the signal scout memo, evaluate candidate topics against the Dataway mission.

Run ID: {contract.run_id}

Existing state:
{prior_state}

For each promising candidate, determine:
- why it matters now
- analyst relevance
- the Dataway teaching angle
- prerequisites
- whether it belongs in the curriculum now, later, or only on a watchlist
- a 0-10 overall score

Do NOT optimize for generic viral content. Search interest is a signal, not the curriculum.
Prefer durable concepts that help an analyst understand the modern data stack and that
can be explained with a tabular dataset or paragraph/document.

If a candidate is a tool/product, identify the underlying durable concept rather than
making the product itself the lesson.
""",
        expected_output="A ranked list of candidate Dataway topics with reasoning and scores.",
        agent=analyst,
        context=[scout_task],
    )

    gate_task = Task(
        description=f"""
You are the curriculum gate for Dataway.

Run ID: {contract.run_id}

Persistent curriculum definition:
{curriculum_definition()}

Existing state:
{prior_state}

Review the scout and analyst-lens outputs.

Rules:
1. First attempt to map the strongest candidate to an existing curriculum topic.
2. A product, company, framework, demo or current event is NOT automatically a curriculum topic.
3. If a signal is a subtopic/example/tool, attach it to the underlying existing concept.
4. Only choose new-branch when the candidate is a durable concept that cannot reasonably
   be taught under an existing topic.
5. Preserve the curriculum sequence and prerequisites.
6. Choose exactly ONE canonical subject for the downstream research stage.
7. The decision must be one of: existing-topic, new-branch, watch, defer, reject.

The selected subject becomes immutable for downstream research. Downstream agents may
use other signals as examples or evidence, but they may not silently replace the subject.

Return a structured CurriculumDecision.
""",
        expected_output="A valid CurriculumDecision selecting exactly one canonical curriculum subject.",
        agent=gate,
        context=[scout_task, lens_task],
        output_pydantic=CurriculumDecision,
    )

    discovery_crew = Crew(
        agents=[scout, analyst, gate],
        tasks=[scout_task, lens_task, gate_task],
        process=Process.sequential,
        verbose=True,
    )

    discovery_result = discovery_crew.kickoff()
    if not discovery_result.pydantic:
        raise RuntimeError("Curriculum gate did not return the expected structured decision")

    decision = discovery_result.pydantic
    contract.lock_candidate(
        candidate_id=decision.candidate_id,
        candidate_title=decision.candidate_title,
        curriculum_topic_id=decision.curriculum_topic_id,
        curriculum_title=decision.curriculum_title,
        curriculum_position=decision.curriculum_position,
        decision=decision.decision,
    )

    locked_contract = contract.prompt_block()

    research_task = Task(
        description=f"""
Research ONLY the locked Dataway curriculum subject below.

LOCKED RUN CONTRACT
{locked_contract}

This contract is authoritative for this stage. You may use products, companies, tools,
papers and current events as evidence, examples or demonstrations, but you MUST NOT
replace the locked subject with one of them.

Find high-quality sources that the creator can actually study. Include:
- official documentation where available
- original research/papers when relevant
- one strong explanatory source
- a useful practical/demo source when available

Also identify the concepts the creator must understand before teaching this topic.
Avoid duplicate sources already in the existing state unless they contain meaningful
new information. Do not fabricate URLs.

Existing source registry:
{prior_state}
""",
        expected_output="A source-backed research brief for the locked curriculum topic, with URLs and learning prerequisites.",
        agent=researcher,
        context=[scout_task, lens_task, gate_task],
    )

    synthesis_task = Task(
        description=f"""
Synthesize today's outputs into the DailyResearch schema.

LOCKED RUN CONTRACT
{locked_contract}

The contract defines the canonical subject. Do not substitute a tool, product or trend
for that subject. Preserve the curriculum identity in every selected topic.

Rules:
- Include only topics that have enough evidence to be useful.
- Include URLs exactly as discovered; never invent or alter them.
- Keep topics distinct from sources.
- Signals may be retained as signals even when they are not curriculum topics.
- The daily summary should tell the creator what changed and what deserves attention.
- recommended_next_topics should contain at most 5 topic IDs/names.
""",
        expected_output="A valid DailyResearch object.",
        agent=researcher,
        context=[scout_task, lens_task, gate_task, research_task],
        output_pydantic=DailyResearch,
    )

    research_crew = Crew(
        agents=[researcher],
        tasks=[research_task, synthesis_task],
        process=Process.sequential,
        verbose=True,
    )

    result = research_crew.kickoff()
    if not result.pydantic:
        raise RuntimeError("Daily research did not return the expected structured output")

    daily = result.pydantic
    result_dict = daily.model_dump()
    merge_daily_result(state, result_dict, today)
    state["last_run_contract"] = contract.as_dict()
    save_state(state)

    report = f"# Dataway Daily Research — {today}\n\n"
    report += f"**Run ID:** `{contract.run_id}`\n\n"
    report += f"**Locked curriculum topic:** {contract.curriculum_title} (`{contract.curriculum_topic_id}`)\n\n"
    report += f"**Curriculum decision:** {contract.decision}\n\n"
    report += f"**Gate rationale:** {decision.rationale}\n\n"
    report += f"{daily.daily_summary}\n\n"
    report += "## Recommended topics\n\n"
    for topic in daily.topics:
        report += f"### {topic.name} — {topic.score:.1f}/10\n"
        report += f"**Why now:** {topic.why_now}\n\n"
        report += f"**Analyst relevance:** {topic.analyst_relevance}\n\n"
        report += f"**Dataway angle:** {topic.dataway_angle}\n\n"
        if topic.prerequisites:
            report += "**Prerequisites:** " + ", ".join(topic.prerequisites) + "\n\n"

    report += "## Signals discovered\n\n"
    for signal in daily.signals:
        url = f" — {signal.url}" if signal.url else ""
        report += f"- **{signal.title}** — {signal.signal_type}{url}\n  {signal.relevance}\n"

    report += "\n## Sources discovered\n\n"
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
