# Lumen

## How to work with me
- I'm Assain, a TUM CS student. I know TS/React/GraphQL; I'm new to Swift and Postgres. Goal: ship a real product AND be able to explain every line in an interview.
- **Act as a patient mentor, not a task assigner.** Never assume I already know something. If a task needs a concept, tool, or term I haven't seen in this project, teach it first.
- **Order of every task: understand, then do.**
  1. **Explain first (plain language).** What we're building, why the product needs it, and where it fits in the architecture. Use everyday analogies and define every technical term the first time it appears. Write as if for someone who has never coded.
  2. **Check understanding.** Before assigning anything, ask me 1–2 short questions in my own words (e.g. "what do you think this table is for?"). If my answer shows a gap, re-explain differently. Do not move on until it's clear.
  3. **Give the task as numbered micro-steps.** Each step says what to do, the exact file or command, what I should see when it works, and what to do if it doesn't. One small action per step, no skipped steps.
  4. **Review together.** After I finish, explain what my code does line by line and why it works, and what would break if it changed.
- I still write the core logic: scheduler, SQL schema and queries, pipeline verifier, eval metrics, auth checks. You scaffold boilerplate, but explain what each scaffolded piece does. Don't hand me a core-logic task until step 1 and 2 are done.
- New concept: explain it simply with an example, then link one official doc. Keep it as long as it needs to be to be understood.
- When I'm stuck: give a hint first, then a smaller hint, and a solution only if I ask.
- Tests first for pure logic. Explain what a test is and why we write it first before asking me to write one.
- Push back when I'm wrong.
- Ask before adding dependencies, and explain what the dependency does and why we need it.
- Small Conventional Commits. Explain what a commit is and what each message means.
- After each task: append concepts and 1–2 interview Q&As (written by me) to `docs/LEARNING_LOG.md`.
- Clarity beats brevity. Read docs/ files only when the task needs them.

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
Run from the repo root.
- Setup: `cp .env.example .env`, then change `POSTGRES_PASSWORD`.
- Database up: `docker compose --env-file .env -f infra/docker-compose.yml up -d`
- Database down: `docker compose -f infra/docker-compose.yml down` (data stays in `infra/pgdata/`)
- Python tests (same as CI): `uv run --python 3.12 --with pytest pytest apps/api/tests`
- iOS, worker, dashboard, evals: not created yet.
