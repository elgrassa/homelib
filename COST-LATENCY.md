# COST-LATENCY.md

Live path timings from **tonight’s Groq** stack (`LLM` via
`GROQ_API_KEY`, model `llama-3.3-70b-versatile`). Do **not** cite Observatory
“Latency p50 / p95” bars that read hung `query_log.latency_ms` (hundreds of
thousands of ms = timeout poison).

## Live Groq table (fill from smoke)

| Path | wall ms | prompt tok | completion tok | cost_usd | notes |
|---|---:|---:|---:|---:|---|
| Ask (grounded, e.g. Walden) | | | | | |
| Ask (`what do you have?` / #A1) | | | | | refuse + shelf line |
| Mentor (#M1 out-of-corpus) | | | | | abstain ≤2 rounds |
| Mentor (in-corpus goal) | | | | | or timed out / degraded |

p50 / p95: compute from the Ask sample above only (n small — say so).

Tokens / USD: AskResponse / Observatory `query_log.cost_usd` when
`LLM_PRICE_PER_1K_*` set; otherwise tokens only.

## Local Ollama vs Groq (DACH sentence)

| Choice | When |
|---|---|
| **Ollama** (`--profile local-llm`, `LLM_API_KEY=ollama`) | Sovereignty, offline, EU data residency, no cloud subprocessor for chat |
| **Groq** (`GROQ_API_KEY`, blank `LLM_API_KEY`) | Demo / reviewer latency, Streamlit Cloud, free-tier RPM |

Same `OpenAIClient` / `LLM_*` seam — no ProviderChain, no second SDK.
