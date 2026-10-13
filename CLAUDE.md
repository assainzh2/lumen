# Lumen

## How to work with me
- I'm Assain, a TUM CS student. I know TS/React/GraphQL; I'm new to Swift and Postgres. Goal: ship a real product AND be able to explain every line in an interview.
- I write the core logic: scheduler, SQL schema and queries, pipeline verifier, eval metrics, auth checks. You scaffold boilerplate.
- New concept: give a ≤5-line explanation plus one official doc link.
- When I'm stuck: give a hint first, then a smaller hint, and a solution only if I ask.
- Tests first for pure logic.
- Push back when I'm wrong.
- Ask before adding dependencies.
- Small Conventional Commits.
- After each task: append concepts and 1–2 interview Q&As (written by me) to `docs/LEARNING_LOG.md`.
- Keep responses short. Read docs/ files only when the task needs them.

## Product
- A calm iPhone widget that rotates facts, mental models, micro-actions and reflection prompts at fixed daily slots.
- Not addictive: no feed, no streaks, no notifications, skip capped at 2.
- Works fully offline.
- **App users never log in.** Auth exists only for the admin dashboard and admin API endpoints.
- Never invent facts. Every content item carries a source.

## Architecture (monorepo)
- `apps/ios` — SwiftUI + WidgetKit, iOS 17+. Downloads signed content packs, otherwise offline.
- `apps/api` — Python 3.12, FastAPI, Postgres + pgvector, Alembic, hand-written SQL.
- `apps/worker` — content pipeline, running as a Postgres job queue: ingest sources → generate with citation → verify → dedupe → review.
- `apps/dashboard` — Next.js admin review UI.
- `packages/evals` — labeled set + metrics, run in CI.
- `infra/` — docker-compose.

## Docs (read on demand)
- `docs/SCHEDULER_SPEC.md` — the deterministic scheduler. Read it before touching scheduling code.
- `docs/ROADMAP.md` — phases and the current task.
- `docs/adr/` — architecture decision records. ADR-001's product rules still apply: anti-addiction rules, widget families, buttons, config intent, app screens. Only its distribution and storage parts are superseded.

## Defaults
- Python: uv, ruff, pytest.
- Secrets live in `.env` and are never committed.
- The repo is public, so never commit keys, tokens or personal data.
- Open questions are listed in ROADMAP.md and SCHEDULER_SPEC.md. Don't decide them silently; raise them with me when their phase starts.

## Commands
(fill in as created)
