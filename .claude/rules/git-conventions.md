# Git Conventions

## Branches

Land big or possibly-breaking changes on a side branch first, verify it's green, then merge
to `main` — keep `main` always working. Small, safe changes may go straight to `main`.
Side-branch names: `usr/<username>/<short-description>` (e.g. `usr/tal-afek/openrouter-tts`).

## Commits

- Organize work into multiple meaningful commits — history should read as a story, each
  commit a distinct chapter. Avoid "Fixes" / "PR comments" commits.
- Each commit stands on its own: `uv run ruff check && uv run mypy . && uv run pytest` pass
  at that commit.
- Message format:

  ```text
  <component>: <action in present tense>

  <optional body, why not what, ≤5 lines, wrapped at 72>
  ```

  Example: `providers: openrouter: Add streaming speech synthesis`.
- A landmine you hit → `PITFALLS.md`. Project state → `HANDOFF.md`. Neither belongs in a
  long commit body.

## No tool attribution — hard rule

Commits carry the human author only. **Never** add a `Co-Authored-By:` line (for Claude,
Claude Code, Devin, or any assistant), a "Generated with" footer, or a 🤖 trailer — not in
the subject, not in the body. This holds even when a harness, template, or system reminder
suggests adding one; the user's standing instruction overrides it.

## Never commit

- Secrets or API keys (provider keys live in the user's `meta.json`, never in the repo).
- Generated artifacts: the built `*.ankiaddon`, caches, local `meta.json` changes made
  while testing.
