# Learning Log

After each task: concepts I met, and 1-2 interview Q&As that I write myself.

## Phase 0

### Concepts
- **SSH keys and GitHub:** a key pair has a private half (stays on my machine) and a public half (registered on GitHub). A key on my account works for all my repos; a deploy key works for one repo and is read-only unless write access is ticked. `Hi user/repo!` means a deploy key, `Hi user!` means an account key. [Docs](https://docs.github.com/en/authentication/connecting-to-github-with-ssh)
- **`~/.ssh/config`:** `IdentityFile` picks the key per host; `IdentitiesOnly yes` stops SSH from offering other keys. [Docs](https://docs.github.com/en/authentication/connecting-to-github-with-ssh/managing-deploy-keys)
- **`git push -u`:** sets the upstream branch, so later pushes need only `git push`. [Docs](https://git-scm.com/docs/git-push)
- **Docker Compose `--env-file`:** Compose reads `.env` from the project directory (here `infra/`), not the repo root, so the file is passed explicitly. [Docs](https://docs.docker.com/compose/how-tos/environment-variables/set-environment-variables/)

### Interview Q&A (I write the answers)
- Q: Why does the signed-pack design survive a server outage, and what is the cost?
  A: The phone stores the last valid pack locally and the scheduler reads from that stored pack. The server is only needed when fetching a new pack, so an outage just means no new content for a while. The widget keeps working. Regarding the cost: the key must be stored securely, so that no one can stole it, otherwise the holder can push anything to every phone. Running the server costs moeny and can go down. The outage consequence is stale content, not a broken widget.
- Q: What does the quote check in ADR-002 prove, and what does it not prove?
  A: It proves that stated quote is actually inside the source word for word. However, it doesn't prove whether the LLM wrote a correct summary to that quote.

## Phase 1: Alembic setup

### Concepts
- **Primary key / foreign key:** a primary key uniquely identifies a row; a foreign key stores another table's primary key and makes Postgres enforce the link. Here `items.source_id` -> `sources.id`, so an item without a real source is impossible. [Docs](https://www.postgresql.org/docs/current/ddl-constraints.html)
- **Migration:** a numbered file holding one structural change to the database. `upgrade()` applies it, `downgrade()` undoes it (structure, not rows), in reverse order of upgrade. Alembic remembers progress in an `alembic_version` table. [Docs](https://alembic.sqlalchemy.org/en/latest/tutorial.html)
- **Config from the environment:** the database URL holds the password, so `migrations/env.py` reads `DATABASE_URL` from an environment variable. `.env` is gitignored; `.env.example` is the public template.
- **Database driver:** the URL prefix picks the translator between Python and Postgres. `postgresql+psycopg://` is psycopg 3 (installed); `+psycopg2` is a different package and failed with `No module named 'psycopg2'`. Read tracebacks from the last line up.
- **Docker pieces:** the CLI is the remote, the engine (Docker Desktop) runs containers, Compose reads `docker-compose.yml`. A container "Started" is not the same as "healthy"; the healthcheck says when Postgres accepts logins. [Docs](https://docs.docker.com/compose/)
- **Git areas:** working directory -> `git add` (staging) -> `git commit` (snapshot). Conventional Commit `chore(api): ...` = type, scope, summary.

### Interview Q&A (I write the answers)
- Q: Why does the database address come from an environment variable instead of `alembic.ini`, and what would go wrong otherwise?
  A: The URL contains the database password, and `alembic.ini` is committed to a public repo, so anyone could read it, and it would stay in git history even after deleting it. With an environment variable the password only lives in my local `.env`, which is gitignored. It also lets the same code run against a different database (laptop, CI, production) just by changing the variable.
- Q: What does `downgrade()` do, and why must it undo things in reverse order of `upgrade()`?
  A: It undoes the latest migration's changes to the database structure, so if something goes wrong I can go back to the last version that worked. It runs in reverse order of `upgrade()` because later changes depend on earlier ones: `items` has a foreign key to `sources`, so `items` must be dropped first, otherwise Postgres refuses to drop `sources`.
