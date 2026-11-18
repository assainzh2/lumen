# Roadmap

Backend and AI come first, for interview stories. The iOS spike is done early to de-risk.

**Current phase: 1**

## Phase 0
- Public GitHub repo from day 1, with a README that states the goal.
- Repo skeleton.
- docker-compose with Postgres + pgvector.
- CI hello-world.
- ADR-002 (supersedes ADR-001): drop SideStore and Scriptable; pay €99 when shipping.
- iOS spike: free signing + widget + App Group sharing on my iPhone.

## Phase 1
- Schema: sources, chunks, items, kinds, reviews, packs, jobs, admin users.
- Alembic migrations.
- FastAPI API with admin auth.
- Integration tests against real Postgres.
- Decided in the reviews task, enforce in the API step:
  - `reviews` is append-only: the API's database role gets only SELECT and INSERT on `reviews` (no UPDATE/DELETE), so history and `decided_at` can't be rewritten.
  - Items never change after creation: an edit creates a new item and the old one gets rejected. Same mechanism: no UPDATE on `items` for the API role.
- Open question (revisit after real reviewing): switch `reviews.reason` from free text to fixed categories once rejection reasons repeat. Needs a migration that maps existing text to categories.

## Phase 2
- Pipeline worker:
  - Postgres job queue (`FOR UPDATE SKIP LOCKED`).
  - Retries and idempotency.
  - LLM provider interface.
  - Rate limiting and a cost budget per run.
- Licensing: store attribution for every source, paraphrase, quotes only from public-domain authors.
- Eval set of ~150 labeled items, in CI. Metrics:
  - factual precision
  - citation validity
  - duplicate rate
  - reviewer rejection rate

- Open questions (decide at the start of Phase 2):
  - Content sources: which ones (e.g. Wikipedia is CC BY-SA, Project Gutenberg is public domain) and their attribution rules.
  - LLM provider and monthly budget cap.
  - Embedding model and vector dimension (the `chunks` and dedupe columns need a fixed size), chosen together with the LLM provider.
  - Ed25519 signing key: where the private key lives, the public key embedded in the app, and a rotation plan.

## Phase 3
- Next.js dashboard: admin login, review queue with source side by side, schedule preview.
- End-to-end tests.

## Phase 4
- iOS Core: scheduler per `SCHEDULER_SPEC.md`, with property tests.
- Pack download with ETag and Ed25519 signature check; keep the last valid pack.
- Widgets: home S/M/L and lock-screen rectangular/inline.
- Intents: favorite, skip.
- App screens: Today / Saved / About.

## Phase 5
- Observability: structured logs, request IDs, metrics.
- Deploy.
- Opt-in anonymous ♥/skip aggregates, with no user IDs.
- Design doc: "Lumen at 100k users".
- Privacy policy (GDPR) and App Store privacy labels. These are required before the App Store, especially once feedback exists.
- €99 → TestFlight → App Store.
