from __future__ import annotations

import os

from crewai import Agent, Crew, LLM, Process, Task
from crewai_tools import TavilySearchTool


DATAWAY_CURRICULUM = """
Dataway mission: help data professionals understand and adapt to the modern data stack, from analytics and data engineering to AI.

Target learner: a working/aspiring analyst who knows some combination of Excel, SQL, Python, BI, automation and basic data engineering, but does not want to become an ML researcher merely to understand AI.

Current AI learning spine (use as the default sequence):
1. Why AI is changing analytics
2. What is an LLM? Data -> ML -> LLM
3. How LLMs process information / tokens
4. Tokenization
5. Context windows and prompting
6. Why hallucinations happen
7. Embeddings / semantic meaning
8. Vector databases vs standard databases
9. RAG
10. Agents
11. Tools and tool calling
12. MCP
13. Evaluation / guardrails
14. AI-native analytics, BI and enterprise workflows

Related data-engineering and analytics pillars remain important: warehousing, data modeling, ETL/ELT, lakes/lakehouses, Spark, Delta Lake, Airflow, Kafka and Databricks. They may be researched independently, but AI learning must not be used as an excuse to jump randomly into advanced infrastructure.

Teaching constraints:
- Start from something an analyst already understands.
- Introduce one new abstraction at a time.
- Explain why a technology exists before how to use it.
- Prefer a concrete problem over a definition.
- Prefer a familiar tabular dataset or paragraph/document as the teaching object.
- Code is optional; it must not be a prerequisite for conceptual understanding.
- Explicitly identify where analogies break.
- The creator must understand the concept before publishing.
- Search interest affects discovery and packaging, not the curriculum.
"""


def build_llm() -> LLM:
    model = os.getenv("DATAWAY_LLM_MODEL", "ollama/qwen3:8b")
    kwargs = {"model": model}
    if model.startswith("ollama/"):
        kwargs["base_url"] = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    return LLM(**kwargs)


def build_research_tool() -> TavilySearchTool:
    if not os.getenv("TAVILY_API_KEY"):
        raise RuntimeError("TAVILY_API_KEY is not set.")
    return TavilySearchTool()


def build_crew(state_snapshot: str) -> Crew:
    llm = build_llm()
    research_tool = build_research_tool()

    topic_scout = Agent(
        role="Dataway Signal Scout",
        goal="Find current signals that can improve Dataway's learning roadmap without letting industry hype dictate the curriculum.",
        backstory=f"""You are the discovery layer, not the curriculum owner. Find current developments, recurring questions, new tools, useful explanations and meaningful changes across AI, analytics and data engineering. A signal can be interesting without being suitable to teach now. Never equate popularity with curriculum priority.\n\n{DATAWAY_CURRICULUM}""",
        tools=[research_tool], llm=llm, verbose=True,
    )

    analyst_lens = Agent(
        role="Dataway Analyst Relevance Gate",
        goal="Determine whether a signal is genuinely worth learning now for Dataway's target analyst.",
        backstory=f"""You are a strict gatekeeper. Your audience already understands common analyst workflows: tables, SQL, Python, BI, dashboards, automation and basic pipelines. Evaluate a topic from that starting point.\n\nA topic may be marked research-now ONLY when it passes most of these tests: (1) clear analyst problem or capability, (2) understandable bridge from existing analyst knowledge, (3) useful conceptual unlock for later Dataway topics, (4) reasonable prerequisite burden for the current position, (5) demonstrable with a tabular dataset, paragraph/document, whiteboard or familiar workflow, and (6) enough evidence to research it properly.\n\nIf a topic is important but premature, mark watch or defer. If it is merely adjacent, generic AI news, regulation, infrastructure or engineering optimization with no immediate analyst learning value, reject or defer. Do not let a high trend score override the gate.\n\n{DATAWAY_CURRICULUM}""",
        llm=llm, verbose=True,
    )

    curriculum_mapper = Agent(
        role="Dataway Curriculum Gatekeeper",
        goal="Protect the sequence and connected mental model of Dataway.",
        backstory=f"""You own sequencing. Compare every accepted candidate against the current learning spine. Identify the nearest prerequisite, current position and downstream concepts. If the candidate skips foundational concepts, explicitly block it from research-now and place it in watch/defer. New branches are allowed only when they clearly connect to an analyst problem and do not disrupt the main learning path.\n\n{DATAWAY_CURRICULUM}""",
        llm=llm, verbose=True,
    )

    source_scout = Agent(
        role="Dataway Source Scout",
        goal="Find authoritative sources only for topics that survived the curriculum gates.",
        backstory="""Find primary documentation, papers, strong technical talks and authoritative explanations. Do not spend research effort on rejected/deferred topics. For a surviving topic, find sources that help the creator understand it rather than sources that merely provide SEO summaries.""",
        tools=[research_tool], llm=llm, verbose=True,
    )

    learning_researcher = Agent(
        role="Dataway Learning Researcher",
        goal="Teach the creator first so the creator can later teach the audience.",
        backstory="""Build progressive learning briefs. Start with the analyst's mental model, then introduce the new abstraction. Include why it exists, how it works, misconceptions, where analogies fail, what the creator should verify, and a possible tabular or document demonstration. Never pretend the creator understands a topic merely because sources were found.""",
        tools=[research_tool], llm=llm, verbose=True,
    )

    content_architect = Agent(
        role="Dataway Content Architect",
        goal="Turn sufficiently understood topics into focused educational plans.",
        backstory="""Design one-question lessons, not generic scripts. Use a whiteboard sequence and a familiar dataset/document demonstration. Content must be downstream of creator understanding. If the learning brief is insufficient, mark not-ready.""",
        llm=llm, verbose=True,
    )

    evaluator = Agent(
        role="Dataway System Evaluator",
        goal="Detect curriculum drift and improve future research behavior without changing Dataway's mission.",
        backstory=f"""Be skeptical. Penalize trend-chasing, advanced-topic jumps, weak analyst fit, unsupported claims and duplicate research. A good run should become more aligned with the Dataway learning spine over time. You may recommend bounded changes to discovery and ranking, but may not rewrite the mission or audience.\n\n{DATAWAY_CURRICULUM}""",
        llm=llm, verbose=True,
    )

    state_keeper = Agent(
        role="Dataway State Keeper",
        goal="Persist useful signals, decisions, sources, queues and bounded feedback as durable memory.",
        backstory="""Maintain compact long-term memory. Keep discovered signals even when they are deferred or rejected, because repeated signals can become relevant later. Store selected topics separately from raw signals. Never erase useful prior state merely because a new run is different.""",
        llm=llm, verbose=True,
    )

    scout_task = Task(
        description=f"""Run today's discovery pass. Search current sources for signals relevant to Dataway. Search broadly enough to discover useful topics, but remember that discovery is not selection. Return candidate signals with evidence, URLs, why the signal matters, and a preliminary action.\n\n{DATAWAY_CURRICULUM}\n\nPersistent state:\n{{state_snapshot}}""",
        expected_output="A concise candidate signal list with evidence, source URLs, novelty and preliminary action.",
        agent=topic_scout,
    )

    lens_task = Task(
        description="""Apply the strict Dataway Analyst Relevance Gate to every candidate. For each candidate provide: analyst problem, bridge from known skills, learning unlock, prerequisite burden, demo potential, curriculum position, analyst relevance score, and status. Status must be exactly one of research-now, watch, defer, reject. Do not use research-now merely because the topic is important, popular or technically impressive.\n\nPersistent state:\n{state_snapshot}""",
        expected_output="Ranked candidates with explicit gate results and status.",
        agent=analyst_lens, context=[scout_task],
    )

    curriculum_task = Task(
        description="""Act as the final curriculum gate. Take only candidates proposed as research-now and verify their position in the current Dataway sequence. If a candidate requires a missing prerequisite, downgrade it to watch/defer. Prefer the next logical concept in the spine over a more advanced but unrelated topic. Return the final research-now set and explain any downgrade.""",
        expected_output="Final curriculum decision with research-now topics, downgraded topics, prerequisites and sequence rationale.",
        agent=curriculum_mapper, context=[lens_task],
    )

    source_task = Task(
        description="""Research sources ONLY for the final research-now set. Find authoritative sources and complementary explanations. Avoid wasting source research on deferred/rejected candidates. Include URL, title, source type, authority, what the creator should learn from it, and recommended order.""",
        expected_output="Source plan for final research-now topics only.",
        agent=source_scout, context=[curriculum_task],
    )

    learning_task = Task(
        description="""Create creator-first learning briefs for the final research-now topics. The brief must answer: what is it, why does it exist, how does it work at a conceptual level, how does it connect to analyst knowledge, what misconceptions matter, where does the analogy break, what should the creator verify, and how can it be demonstrated with a familiar table or document? Do not write a final script.""",
        expected_output="Creator-first learning briefs with source-backed claims and demo ideas.",
        agent=learning_researcher, context=[source_task],
    )

    content_task = Task(
        description="""Create content plans only for topics whose learning briefs are sufficiently grounded. Each plan should have one focal question, whiteboard sequence, dataset/document demonstration, private talking points, and optional YouTube/X packaging. Mark uncertain topics not-ready.""",
        expected_output="Focused content plans plus explicit not-ready topics.",
        agent=content_architect, context=[learning_task],
    )

    eval_task = Task(
        description="""Evaluate the complete run. Specifically measure curriculum drift, false-positive research-now decisions, duplicate signals, source quality, unsupported claims and whether the run respected the analyst-first demonstration model. Give bounded recommendations for the next run.""",
        expected_output="Evaluation metrics, failures, lessons and bounded course-correction recommendations.",
        agent=evaluator, context=[scout_task, lens_task, curriculum_task, source_task, learning_task, content_task],
    )

    state_task = Task(
        description="""Create the durable state update. Return ONLY valid JSON using this exact shape:\n{\n  \"topics\": {},\n  \"sources\": {},\n  \"signals\": {},\n  \"research_queue\": [],\n  \"learning_queue\": [],\n  \"content_queue\": [],\n  \"feedback\": {},\n  \"system_metrics\": {}\n}\n\nImportant: persist ALL meaningful discovered signals, including watch/defer/reject decisions. Topic records must contain status, curriculum_position, prerequisites, downstream_concepts, scores and last_seen. Signal records should contain title, topic_id if applicable, status, evidence URLs and last_seen. Queue entries should use topic identifiers. Feedback should preserve bounded evaluator lessons. Do not delete useful existing records.\n\nCurrent persistent state:\n{state_snapshot}""",
        expected_output="Valid JSON only with the required top-level keys.",
        agent=state_keeper,
        context=[scout_task, lens_task, curriculum_task, source_task, learning_task, content_task, eval_task],
    )

    return Crew(
        agents=[topic_scout, analyst_lens, curriculum_mapper, source_scout, learning_researcher, content_architect, evaluator, state_keeper],
        tasks=[scout_task, lens_task, curriculum_task, source_task, learning_task, content_task, eval_task, state_task],
        process=Process.sequential,
        verbose=True,
    )
