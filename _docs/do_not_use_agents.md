# agents.md — Claude Agent Guide for JobMatch AI

How to use Claude Code's agent system effectively in this repo.
Read alongside `CLAUDE.md` (commands, layout, invariants) and `architecture.md` (system diagram).

---

## When to spawn an agent

The main Claude instance should handle most work inline. Spawn a subagent only when:

- **Broad exploration** — finding where a concept (e.g. "scoring", "adzuna") lives across the whole tree. Use `subagent_type: Explore`.
- **Independent parallel work** — two unrelated tasks (e.g. writing a backend test while reading frontend source). Launch both in the same message.
- **Protecting context** — a task would dump large file contents into the main window (e.g. reading every migration file). Delegate to a subagent and get back a summary.
- **Architecture / plan design** — before implementing a non-trivial feature. Use `subagent_type: Plan`.

Do NOT spawn an agent when a single `grep` or `Read` call would answer the question — subagents start cold and are expensive.

---

## Agent types in use

| Type | When to use in this repo |
|---|---|
| `Explore` | Locating symbols, understanding naming conventions, mapping which file owns a behaviour |
| `Plan` | Designing the approach for a new module (e.g. how to structure the normalize layer) before writing code |
| `claude` (general) | Multi-step tasks that need both reads and writes and don't fit the above |

---

## Briefing a subagent — checklist

A subagent starts with no conversation history. The prompt must be self-contained:

1. **State the goal** — one sentence on what it should accomplish.
2. **Give the relevant file paths or module names** — don't make it rediscover things you already know.
3. **State what you've already ruled out** — avoids redoing work.
4. **Say whether it should read or write** — Explore agents should not edit files.
5. **Cap the response** — for research tasks, ask for a short summary (e.g. "report in under 200 words") to keep the result usable.

---

## Repo-specific context to include in agent prompts

Always tell a subagent the parts of CLAUDE.md it needs:

- **Stack**: FastAPI backend (`backend/`), React + Vite frontend (`frontend/`), Supabase (hosted Postgres), OpenAI for re-ranking, Docker Compose local only.
- **Key invariant**: jobs dedup on `(source, external_id)`; Pass 2 (OpenAI) only runs on top 15–20 Pass 1 results; all external calls live in the backend.
- **Test rule**: no live network calls in tests — source clients and OpenAI are always mocked.
- **Scoring weights**: skills 40%, seniority 20%, location 20%, salary 20% — don't change without being asked.

---

## Common agent patterns

### Pattern 1 — Locate then implement

```
1. Spawn Explore agent:
   "Find where Adzuna normalization is handled in backend/.
    Report the file path and the function signature. Under 100 words."

2. Use the result to read exactly the right file inline,
   then implement the change yourself.
```

### Pattern 2 — Parallel independent tasks

When two issues are truly independent (e.g. #8 Adzuna client + #9 Jooble client),
send one message with two Agent tool calls. Both receive the same repo context.
Collect both results before writing any code — one may reveal a shared interface
the other should conform to.

### Pattern 3 — Plan before a complex module

```
Spawn Plan agent before implementing pipeline.py or pass2.py:
"Design the module interface for <X> in this FastAPI project.
 Context: [paste relevant CLAUDE.md sections].
 Return: proposed function signatures, data flow, and one paragraph
 on error-handling approach. No code yet."

Review the plan, adjust if needed, then implement inline.
```

---

## What agents should NOT do

- **Edit files without being told to** — Explore agents are read-only by definition.
- **Make live API calls** (Adzuna, Jooble, OpenAI, Supabase) — even in research mode; use recorded fixtures.
- **Widen Canada scope** — any query against a source must keep the Canada filter.
- **Remove the Pass 2 cap** — 15–20 jobs max to OpenAI; flag if a task seems to require more.

---

## Parallelism rules

- Independent tasks in the same GitHub issue group can be delegated in parallel.
- Tasks with a shared data contract (e.g. normalize → persist → score) must be sequenced or given an agreed-upon interface stub upfront.
- Never run two agents that both write to the same file simultaneously.
