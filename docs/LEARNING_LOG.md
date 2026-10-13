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
