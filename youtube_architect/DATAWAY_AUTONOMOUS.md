# Dataway Autonomous Research v1

This branch changes the prototype from a prompt-driven YouTube script generator into a daily Dataway research and learning system.

## What it does

Each run:

1. Discovers current signals across AI, analytics and data engineering.
2. Compares them with persistent Dataway state.
3. Evaluates analyst relevance and learning value.
4. Maps candidates to the Dataway curriculum.
5. Finds sources when a topic deserves research.
6. Builds creator-first learning briefs.
7. Produces content plans only when a topic has enough foundation.
8. Evaluates the run for duplicates, weak sources, hype and curriculum problems.
9. Persists compact topic/source/queue/feedback state.
10. Stores the full daily report under `runs/`.

It does **not** publish content automatically.

## Local run

From `youtube_architect/`:

```bash
uv sync
export DATAWAY_LLM_MODEL="your-configured-model"
export OPENAI_API_KEY="..."       # when using a hosted OpenAI model
export SERPER_API_KEY="..."        # enables current web research
uv run python -m youtube_architect.run_daily
```

For local Ollama development, use a supported Ollama model and set:

```bash
export DATAWAY_LLM_MODEL="ollama/gemma4:latest"
export OLLAMA_BASE_URL="http://localhost:11434"
```

## Daily scheduled run

`.github/workflows/dataway-daily.yml` runs at 09:00 IST and can also be started manually from GitHub Actions.

Configure these repository secrets before enabling the schedule:

- `OPENAI_API_KEY`
- `SERPER_API_KEY`
- `DATAWAY_LLM_MODEL`

The workflow commits the updated state and daily report back to the branch.

## Important design principle

The system has persistent memory, but it does not rewrite its own mission. Course correction is bounded by evaluation criteria and the Dataway vision. The creator remains the final reviewer before a topic becomes published content.
