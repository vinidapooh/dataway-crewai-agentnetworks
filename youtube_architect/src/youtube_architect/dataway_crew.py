from __future__ import annotations

import os

from crewai import Agent, Crew, LLM, Process, Task
from crewai_tools import SerperDevTool


def build_llm() -> LLM:
    """Build the configured LLM. Local Ollama is useful during development; hosted
    models can be selected through DATAWAY_LLM_MODEL in scheduled environments."""
    model = os.getenv("DATAWAY_LLM_MODEL", "ollama/gemma4:latest")
    kwargs = {"model": model}
    if model.startswith("ollama/"):
        kwargs["base_url"] = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    return LLM(**kwargs)


def build_crew(state_snapshot: str) -> Crew:
    llm = build_llm()
    search_tool = SerperDevTool() if os.getenv("SERPER_API_KEY") else None
    research_tools = [search_tool] if search_tool else []

    topic_scout = Agent(
        role="Dataway Topic Scout",
        goal="Discover meaningful developments that could matter to data professionals and fit the Dataway mission.",
        backstory="""You monitor AI, analytics, data engineering and adjacent technical developments.
        Look for meaningful signals rather than generic hype. Compare every discovery with persistent Dataway state
        and prefer updating existing topics when appropriate.""",
        tools=research_tools, llm=llm, verbose=True,
    )
    analyst_lens = Agent(
        role="Dataway Analyst Lens",
        goal="Translate candidate signals into analyst-relevant learning opportunities.",
        backstory="""You understand analysts who know Excel, SQL, Python, BI, automation and basic data engineering.
        Ask what the analyst already knows, what is genuinely new, what problem the technology solves, and what
        prerequisites are needed.""",
        llm=llm, verbose=True,
    )
    curriculum_mapper = Agent(
        role="Dataway Curriculum Mapper",
        goal="Protect the coherence of the Dataway learning graph.",
        backstory="""Identify duplicates, prerequisites, downstream concepts and useful bridges between analytics,
        data engineering and AI. Do not chase a topic simply because it is trending.""",
        llm=llm, verbose=True,
    )
    source_scout = Agent(
        role="Dataway Source Scout",
        goal="Find authoritative and useful sources for promising topics.",
        backstory="""Prefer primary documentation, papers, talks, strong technical explanations and practical material.
        Explain why each source is useful and distinguish primary evidence from commentary.""",
        tools=research_tools, llm=llm, verbose=True,
    )
    learning_researcher = Agent(
        role="Dataway Learning Researcher",
        goal="Create a creator-first learning brief so the creator can understand a topic before teaching it.",
        backstory="""Teach the creator first, not the audience. Explain progressively, connect concepts to analyst
        knowledge, identify misconceptions, and explicitly flag where analogies break down. Prefer a table or
        document demonstration where appropriate.""",
        tools=research_tools, llm=llm, verbose=True,
    )
    content_architect = Agent(
        role="Dataway Content Architect",
        goal="Turn an understood topic into a focused educational plan without writing a generic script.",
        backstory="""Design one-question lessons with a whiteboard sequence, dataset/document demonstration, private
        talking points and packaging options. Content must fit the Dataway teaching philosophy.""",
        llm=llm, verbose=True,
    )
    evaluator = Agent(
        role="Dataway System Evaluator",
        goal="Evaluate the run and propose bounded course corrections.",
        backstory="""Detect duplicates, weak sources, unsupported claims, excessive hype, poor analyst relevance and
        curriculum problems. Propose changes to future research behavior without changing the core mission.""",
        llm=llm, verbose=True,
    )
    state_keeper = Agent(
        role="Dataway State Keeper",
        goal="Convert the useful conclusions of a run into a small, durable state update.",
        backstory="""You maintain Dataway's long-term memory. Store compact topic, source, queue and feedback metadata,
        not giant research documents. Preserve existing records unless there is strong evidence to update them.
        Your output must be valid JSON and must never change the Dataway mission.""",
        llm=llm, verbose=True,
    )

    scout_task = Task(
        description="""Run a daily discovery pass for Dataway.

Persistent state:
{state_snapshot}

Find meaningful developments across AI, analytics, data engineering and adjacent fields. Search current web sources
when tools are available. Identify new signals and updates to existing topics. Do not write scripts. Return a concise,
structured candidate list with evidence and URLs where available.""",
        expected_output="A structured list of candidate signals including novelty, evidence, analyst relevance and recommended action.",
        agent=topic_scout,
    )
    lens_task = Task(
        description="""Evaluate the discovered signals through the Dataway analyst lens. Score each for analyst relevance,
learning value, current interest, evergreen value, demo potential and prerequisite burden. Recommend research-now,
watch, defer or reject. Use the persistent state to avoid duplicates.

Persistent state:
{state_snapshot}""",
        expected_output="Ranked candidate topics with scores, rationale, prerequisites and status.",
        agent=analyst_lens, context=[scout_task],
    )
    curriculum_task = Task(
        description="""Map promising candidates into the Dataway curriculum. Detect duplicates, missing prerequisites and
downstream concepts. Preserve the existing learning path while allowing justified new branches.""",
        expected_output="Curriculum mapping with prerequisite, current position, downstream concepts and sequence recommendation.",
        agent=curriculum_mapper, context=[lens_task],
    )
    source_task = Task(
        description="""For research-now topics, find sources needed to understand them. Prefer primary/authoritative material.
If a source is already present in persistent state, look for updates or complementary sources instead of duplicating it.""",
        expected_output="Source plan for promising topics, including URLs, source type, authority/relevance and recommended order.",
        agent=source_scout, context=[curriculum_task],
    )
    learning_task = Task(
        description="""Build creator-first learning briefs for the strongest research-now topics. Explain what it is, why it exists,
how it works, analyst connections, broken analogies, misconceptions and a possible table/document demonstration.
Clearly distinguish source-backed claims from simplification or inference.""",
        expected_output="Creator-first learning briefs. Do not write final YouTube scripts.",
        agent=learning_researcher, context=[source_task],
    )
    content_task = Task(
        description="""For topics that are sufficiently understood, create a content plan. If a topic is too uncertain or lacks a
solid learning foundation, mark it as not-ready rather than forcing a content plan. For ready topics provide one focal
question, whiteboard sequence, dataset/document demo, private talking points, title angles and X angle.""",
        expected_output="Content plans for ready topics plus explicit not-ready reasons for others.",
        agent=content_architect, context=[learning_task],
    )
    eval_task = Task(
        description="""Evaluate the complete daily run. Identify duplicate discoveries, weak research, unsupported claims, excessive hype,
poor analyst fit, curriculum conflicts and process failures. Provide bounded recommendations for the next run.
Do not rewrite the Dataway mission.""",
        expected_output="Daily evaluation containing metrics, failures, lessons and bounded course-correction recommendations.",
        agent=evaluator, context=[scout_task, lens_task, curriculum_task, source_task, learning_task, content_task],
    )
    state_task = Task(
        description="""Create the durable state update from the full run. Return ONLY valid JSON with this exact top-level shape:
{
  "topics": {},
  "sources": {},
  "research_queue": [],
  "learning_queue": [],
  "content_queue": [],
  "feedback": {},
  "system_metrics": {}
}

Use compact metadata. Topic records should contain status, scores, prerequisites, downstream concepts and last_seen.
Source records should contain url, title, source_type, topic and last_seen. Queues should contain topic identifiers.
Feedback should contain the evaluator's bounded course-correction lessons. Do not delete existing useful state.
Do not include markdown fences or commentary outside the JSON.""",
        expected_output="Valid JSON only using the required top-level shape.",
        agent=state_keeper,
        context=[scout_task, lens_task, curriculum_task, source_task, learning_task, content_task, eval_task],
    )

    return Crew(
        agents=[topic_scout, analyst_lens, curriculum_mapper, source_scout, learning_researcher,
                content_architect, evaluator, state_keeper],
        tasks=[scout_task, lens_task, curriculum_task, source_task, learning_task, content_task, eval_task, state_task],
        process=Process.sequential,
        verbose=True,
    )
