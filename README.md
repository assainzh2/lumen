# Lumen

A calm iPhone widget that rotates facts, mental models, micro-actions and reflection prompts at fixed daily slots.

No feed, no streaks, no notifications. Works fully offline. Every content item carries a source.

## Structure
- `apps/ios`: SwiftUI + WidgetKit app
- `apps/api`: FastAPI backend (Postgres + pgvector)
- `apps/worker`: content pipeline (ingest, generate, verify, dedupe, review)
- `apps/dashboard`: Next.js admin review UI
- `packages/evals`: labeled set and metrics
- `infra`: docker-compose
- `docs`: specs and architecture decision records

## Status
Phase 0: setup. Not usable yet.
