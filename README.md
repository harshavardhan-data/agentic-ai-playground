# Evidence-Backed Analytics System

Python/FastAPI service that runs SQL/Python analysis, validates findings with an LLM, and tracks finding lifecycle.

- **Branch:** `test/ai-reviewer-scope`
- **Status:** core evidence/validation layer complete; master-agent routing and tool registry partially built and deferred

## Implemented
- Deterministic profiling, anomaly detection, and data-quality checks
- LLM validation workflow that re-checks claims by executing SQL/Python
- Finding lifecycle tracking (new → ongoing → resolved/contradicted), confidence scoring, agent memory
- On-demand root-cause investigations that attach supporting evidence to findings

## Deferred
- Master-agent routing / tool registry for multi-agent dispatch — designed and partially built, paused to prioritize the evidence/validation layer

## Tech
Python, FastAPI, SQLAlchemy, SQL, Pandas, LLM APIs