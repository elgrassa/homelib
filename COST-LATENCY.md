# COST-LATENCY.md

Live path timings from Groq free-tier smoke (**provider:** Groq,
**model:** `openai/gpt-oss-20b`, **date:** 2026-09-07). Do **not** cite
Observatory “Latency p50 / p95” bars that read hung `query_log.latency_ms`
(hundreds of thousands of ms = timeout poison).

Observatory USD (when `LLM_PRICE_PER_1K_*` set) is an **estimated list-price
equivalent**, not Groq billed amount — free-tier bill may remain $0.

## Live Groq table

| Path | wall ms | prompt tok | completion tok | cost_usd (list eq.) | notes |
|---|---:|---:|---:|---:|---|
| Ask (Walden) | 16380 | 1595 | 114 | ~0.00015 | grounded; 1+ citation; `degraded=false` |
| Ask (`what do you have?` / #A1) | — | — | — | — | UI refuse + shelf line (no blank) |
| Mentor (#M1 out-of-corpus) | ~2–5s | — | — | — | abstain; tools `[]`; ≤2 rounds |
| Mentor (in-corpus Thoreau goal) | ~2–5s | — | — | — | tools include `search_shelf`; may abstain if shelf miss |

p50 / p95: n=1 Ask sample above — too small to cite as distribution.

List rates used for local evidence (verify at https://groq.com/pricing):
`LLM_PRICE_PER_1K_PROMPT=0.000075`, `LLM_PRICE_PER_1K_COMPLETION=0.00030`.

## Local Ollama vs Groq (DACH sentence)

| Choice | When |
|---|---|
| **Ollama** (`--profile local-llm`, `LLM_API_KEY=ollama`) | Sovereignty, offline, EU data residency, no cloud subprocessor for chat |
| **Groq** (`GROQ_API_KEY`, blank `LLM_API_KEY`) | Demo / reviewer latency, Streamlit Cloud, free-tier RPM |

Same `OpenAIClient` / `LLM_*` seam — no ProviderChain, no second SDK.
