Phase 0, session 1. Context: CLAUDE.md. Read docs/adr/ADR-001.md (the original plan; superseded where CLAUDE.md differs) and docs/SCHEDULER_SPEC.md.

Do these one at a time, and check in with me after each:

1. Explain the architecture back to me in ≤10 bullets. Then quiz me with 3 questions, including why the scheduler indexes by kind-occurrence k, not by globalSlot.
2. ADR-002: I draft it, you critique it. Save it to docs/adr/.
3. Repo skeleton:
   - folders per CLAUDE.md
   - .gitignore
   - README stub
   - infra/docker-compose.yml (Postgres 16 + pgvector)
   - a GitHub Actions workflow with a placeholder test
4. iOS spike: give me step-by-step Xcode instructions (free Apple ID) for a minimal app + widget, and how to check whether App Group sharing works. Explain what each outcome means for the €99 decision.
5. Help me create the public GitHub repo and push. Explain each git command I run.
6. Create docs/LEARNING_LOG.md. Fill in Commands in CLAUDE.md. Propose the Phase 1 schema task (I'll design the schema myself).

My machine: MacBook Pro M1 (2021), Xcode, Git, GitHub.
