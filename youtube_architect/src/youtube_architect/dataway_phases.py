from __future__ import annotations

from crewai import Agent, Crew, Process, Task

from youtube_architect.dataway_crew import DATAWAY_CURRICULUM, build_llm, build_research_tool


def build_discovery_crew(state_snapshot: str) -> Crew:
    llm = build_llm()
    research_tool = build_research_tool()

    scout = Agent(
        role="Dataway Signal Scout",
        goal="Discover current signals without deciding the curriculum.",
        backstory=f"""You are discovery only. Find current developments, questions, tools and meaningful changes across AI, analytics and data engineering. A signal may be interesting without being a lesson. Never equate popularity with curriculum priority.\n\n{DATAWAY_CURRICULUM}""",
        tools=[research_tool], llm=llm, verbose=True,
    )
    analyst = Agent(
        role="Dataway Analyst Relevance Gate",
        goal="Judge whether discovered signals matter to the target analyst.",
        backstory=f"""Be a strict analyst-first gatekeeper. Evaluate the bridge from Excel/SQL/Python/BI knowledge, learning value, prerequisite burden and demonstration potential. Trend alone is never sufficient.\n\n{DATAWAY_CURRICULUM}""",
        llm=llm, verbose=True,
    )
    mapper = Agent(
        role="Dataway Curriculum Gatekeeper",
        goal="Select the next curriculum topic without allowing a signal to hijack the lesson.",
        backstory=f"""You are the final curriculum authority. The persistent curriculum below is authoritative. Map promising signals to EXISTING topic IDs whenever possible. A product, company, tool or trend is evidence or an example, not automatically a lesson. Only select a topic ID that exists in the supplied curriculum. Return exactly one research-now topic or state that none should be researched.\n\n{DATAWAY_CURRICULUM}""",
        llm=llm, verbose=True,
    )

    scout_task = Task(
        description=f"""Run today's discovery scan. Find current signals relevant to Dataway. Return evidence, URLs, novelty and why each might matter. Do not select the curriculum topic yet.\n\nPersistent state:\n{state_snapshot}\n\n{DATAWAY_CURRICULUM}""",
        expected_output="Candidate signals with evidence and URLs.",
        agent=scout,
    )
    analyst_task = Task(
        description=f"""Apply the analyst relevance gate to the scout output. Classify candidates as research-now, watch, defer or reject and explain the reasoning. Do not invent curriculum topics.\n\n{state_snapshot}""",
        expected_output="Ranked candidates with explicit gate decisions.",
        agent=analyst,
        context=[scout_task],
    )
    mapper_task = Task(
        description="""Act as the final curriculum gate. Select at most ONE topic from the persistent curriculum for research-now. You MUST return JSON in exactly this shape and nothing else:
{"research_now":[{"topic_id":"existing-topic-id","rationale":"why this is the next logical topic"}],"downgraded":[],"drift_notes":"..."}

Rules:
- topic_id MUST exactly match an existing persistent topic ID.
- Prefer the next logical topic whose prerequisites are satisfied.
- If the signal is about a tool/product, map it to the underlying curriculum concept.
- Never create a product/tool topic.
- If nothing is ready, return an empty research_now list.
""",
        expected_output="JSON only containing at most one existing curriculum topic ID in research_now.",
        agent=mapper,
        context=[analyst_task],
    )

    return Crew(
        agents=[scout, analyst, mapper],
        tasks=[scout_task, analyst_task, mapper_task],
        process=Process.sequential,
        verbose=True,
    )


def build_research_crew(state_snapshot: str, contract_block: str, curriculum_output: str) -> Crew:
    llm = build_llm()
    research_tool = build_research_tool()

    source = Agent(
        role="Dataway Source Scout",
        goal="Research only the locked canonical curriculum topic.",
        backstory="""You are not allowed to change the lesson subject. Products, companies and current events may be used only as evidence or examples for the locked topic.""",
        tools=[research_tool], llm=llm, verbose=True,
    )
    learner = Agent(
        role="Dataway Learning Researcher",
        goal="Build creator-first understanding of the locked topic.",
        backstory="""Teach the creator first. Start from analyst knowledge, explain why the concept exists, how it works, misconceptions, broken analogies, verification points and a concrete table/document demonstration. Never silently change topics.""",
        tools=[research_tool], llm=llm, verbose=True,
    )
    architect = Agent(
        role="Dataway Content Architect",
        goal="Design a focused lesson for the locked topic only.",
        backstory="""Create one-question lessons with a whiteboard sequence and familiar dataset/document demonstration. If research is insufficient, mark not-ready rather than changing the topic.""",
        llm=llm, verbose=True,
    )
    evaluator = Agent(
        role="Dataway System Evaluator",
        goal="Detect whether the locked topic was respected and identify curriculum drift.",
        backstory=f"""Be skeptical. Penalize subject substitution, trend chasing, unsupported claims, weak analyst fit and unnecessary prerequisite jumps.\n\n{DATAWAY_CURRICULUM}""",
        llm=llm, verbose=True,
    )
    keeper = Agent(
        role="Dataway State Keeper",
        goal="Persist this run without losing prior memory.",
        backstory="""Store the locked topic separately from raw signals. Preserve useful watch/defer/reject signals. Never erase prior state.""",
        llm=llm, verbose=True,
    )

    source_task = Task(
        description=f"""Research ONLY the canonical topic below. Find authoritative sources and complementary explanations.\n\nRUN CONTRACT:\n{contract_block}\n\nCURRICULUM GATE OUTPUT:\n{curriculum_output}\n\nPersistent state:\n{state_snapshot}""",
        expected_output="Authoritative source plan for the locked topic only.",
        agent=source,
    )
    learning_task = Task(
        description=f"""Create a creator-first learning brief for the LOCKED topic. Do not substitute another topic, even if the sources mention an interesting product or trend.\n\nRUN CONTRACT:\n{contract_block}""",
        expected_output="Source-backed learning brief for the locked topic.",
        agent=learner,
        context=[source_task],
    )
    content_task = Task(
        description=f"""Create a content plan for the LOCKED topic only. Include one focal question, whiteboard sequence, familiar dataset/document demonstration, private talking points and optional packaging.\n\nRUN CONTRACT:\n{contract_block}""",
        expected_output="Focused content plan or an explicit not-ready decision.",
        agent=architect,
        context=[learning_task],
    )
    eval_task = Task(
        description=f"""Evaluate the run specifically against the immutable contract below. Check whether every downstream task stayed on the same topic.\n\nRUN CONTRACT:\n{contract_block}""",
        expected_output="Evaluation with drift, evidence quality and bounded recommendations.",
        agent=evaluator,
        context=[source_task, learning_task, content_task],
    )
    state_task = Task(
        description=f"""Return ONLY valid JSON with this exact top-level shape:
{{"topics":{{}},"sources":{{}},"signals":{{}},"research_queue":[],"learning_queue":[],"content_queue":[],"feedback":{{}},"system_metrics":{{}}}}

Persist this run while preserving useful prior state. Record the locked topic under topics and run-specific feedback/metrics. Preserve meaningful discovered signals and their decisions. Queue entries must use topic IDs. Never replace the locked topic with a product or tool.

RUN CONTRACT:\n{contract_block}\n\nPersistent state:\n{state_snapshot}""",
        expected_output="Valid JSON only with the required top-level keys.",
        agent=keeper,
        context=[source_task, learning_task, content_task, eval_task],
    )

    return Crew(
        agents=[source, learner, architect, evaluator, keeper],
        tasks=[source_task, learning_task, content_task, eval_task, state_task],
        process=Process.sequential,
        verbose=True,
    )
