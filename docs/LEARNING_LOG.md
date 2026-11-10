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

## Phase 1: sources and kinds migration

### Concepts
- **Test first (red, then green):** write the test before the code and watch it fail for the *right* reason (here: `assert table_exists(..., "sources")` is `False`, not an import error). A test that has never failed could pass even if the code were wrong, so you could not trust it. The git history shows the story: `test(api): add failing migration round-trip test`, then `feat(api): add migration for sources and kinds tables`.
- **Round-trip migration test:** `downgrade base` -> `upgrade head` -> check the tables exist -> `downgrade base` -> check they are gone. The last two lines are what catch a broken `downgrade()`. An empty `downgrade()` does not break `upgrade`; it breaks the final assert, and poisons the next run ("table already exists").
- **Test database guard:** the fixture refuses any database whose name does not end in `_test`, because `downgrade base` drops tables. Run against the real `lumen` database, it would delete the dev schema.
- **Migration file anatomy:** `revision` is this file's own ID; `down_revision` is the previous file's ID (`None` = first), which chains files into a linked list. `alembic_version` stores the current ID. Alembic runs a migration in one transaction, so a failing one leaves no half-created tables. [Docs](https://alembic.sqlalchemy.org/en/latest/tutorial.html)
- **Why `sources` stores the full text, not just a URL:** pages change or disappear, so the quote check ("the quote appears word for word in the source") must run against our own snapshot. The reviewer's side-by-side view and re-running old verification need it too. The quote itself belongs to the *item*; the source holds the whole text.
- **Lookup table (`kinds`):** a small table of fixed categories that `items` will point to with a foreign key. Postgres then rejects a typo like `'fcat'` for free, with no Python validation.
- **Column pieces used:**
  - `GENERATED ALWAYS AS IDENTITY`: Postgres numbers the rows itself.
  - `PRIMARY KEY`: unique, never empty; foreign keys point at it.
  - `NOT NULL`: the column cannot be empty.
  - `UNIQUE`: no two rows share the value (here: the same URL cannot be stored twice).
  - `DEFAULT now()`: Postgres fills in the current time if none is given.
  - [CREATE TABLE docs](https://www.postgresql.org/docs/current/sql-createtable.html)
- **`timestamptz` vs `timestamp`:** `timestamp` stores a wall-clock reading and drops the zone; `now()` into it is converted to the session's local time, so two machines in different zones store different numbers for the same moment. `timestamptz` stores the absolute instant (normalized to UTC) and shows it in the reader's zone. Use it for "when did this happen". [Docs](https://www.postgresql.org/docs/current/datatype-datetime.html)
- **Naming:** Postgres folds unquoted names to lowercase, so `fetchingDate` became `fetchingdate`. Use `snake_case`, and `..._at` for timestamps (`fetched_at`).
- **Reading a long error:** ignore the Python call stack. Find the first line with the error type (`psycopg.errors.SyntaxError: ...`) and the `LINE n:` below it. Postgres finds grammar mistakes (a trailing comma) before it checks that names and types exist (`URL`, `CURRENT_TIMESTAMPTZ`), so errors show up one layer at a time.
- **What the test does *not* prove:** it only checks that the tables exist. It passed with the wrong type (`timestamp`) and would pass with wrong column names. Column-level checks need inserted rows (the API integration tests later in Phase 1).

### Open questions (not decided yet)
- If the same URL is fetched again and the page changed, `UNIQUE` on `url` allows only one snapshot per URL. Decide in Phase 2.
- The list of kinds differs between CLAUDE.md (facts, mental models, micro-actions, reflection prompts) and ADR-001 / SCHEDULER_SPEC (also intentions, gratitude, review). Decide before scheduler work.

### Interview Q&A (I write the answers)
- Q: Why does the `sources` table store the full text of the page instead of only its URL?
  A: Because the source can change its text or be deleted completely, so we need our own snapshot as proof of what the text said when we used it. The automatic verifier also needs it: it checks that the quote appears word for word in the stored text, and it can only do that against a copy we own. It also helps the human reviewer, who can compare the item's wording with the source side by side without depending on the live page.
- Q: Your migration test is green. What does it prove, and what does it *not* prove?
  A: It proves that, starting from an empty database, `upgrade()` creates the `sources` and `kinds` tables and `downgrade()` removes them again, with no errors. However, it only checks that the tables exist. It doesn't prove the columns have the right names or types (it passed with `TIMESTAMP` instead of `TIMESTAMPTZ`), that `NOT NULL` really rejects empty values, or that `UNIQUE` really rejects a duplicate `url` or `name`, because it never inserts a row. Later tests that insert rows and expect the database to refuse duplicates and empty values would catch those problems. 
