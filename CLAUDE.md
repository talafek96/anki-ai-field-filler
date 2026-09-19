<!--
  Root CLAUDE.md. Keep it thin (aim < 150 lines) — it loads every session.
  Directory-specific detail belongs in a nested CLAUDE.md (providers/, tests/);
  language/git rules live in .claude/rules/. Before adding a line here, ask
  whether the agent could infer it from the code — if so, don't.
  Lint: python .claude/skills/claude-md-standards/scripts/lint_claude_md.py . --opinionated
-->

# AI Field Filler

An **Anki addon** that fills note fields with AI-generated text, audio, and images. It talks
to OpenAI, Anthropic, Google, and OpenRouter through a small provider layer, and ships as a
single `.ankiaddon` package installed into Anki's bundled Python.

## Read these on spawn

You have no memory between sessions. Two files at repo root do — read both before making
changes, and keep them current:

- **`PITFALLS.md`** — every trap already hit and resolved (provider quirks, API shape
  surprises, packaging limits). Append to it whenever you resolve a real defect.
- **`HANDOFF.md`** — where the last session left off and what's in flight. Update it at
  milestones.

`git log` is the history. Deeper design notes: `README.md`, `TESTING.md`.

## Core standards — the constitution

The durable engineering principles below are imported so they are **always in context**. They
**supersede** any other convention or default; a warranted deviation must be justified in
writing at the point of deviation. The short version: pure-Python only, Python 3.9 floor,
capability negotiated at runtime (never from a model id), fail fast and legibly, tests pin
behavior, one way to do a thing.

@.claude/constitution.md

## Stack & layout

- **Stack:** Python 3.9+, PyQt (`aqt`/`anki`), `uv` for env/deps, `ruff` + `mypy`, `pytest`.
- **Layout:** the addon package is **`src/ai_field_filler/`** — its *contents* become the
  installed addon root. Inside it, code is grouped by role:
  - `core/` — domain logic, no Qt: `field_filler.py` (orchestration), `media_handler.py`.
  - `config/` — `config_manager.py` (dataclasses + singleton, `FIELD_TYPES`), `settings_io.py`.
  - `providers/` — the provider layer (own `CLAUDE.md`).
  - `ui/` — Qt dialogs/tabs (own `CLAUDE.md`).
  - `hooks/` — Anki integration: `editor_hooks.py`, `browser_hooks.py`.
  - `__init__.py`, `config.json`, `config.md` stay at the package root (Anki loads them).
  Above the package: `tests/` (own `CLAUDE.md`), `build_ankiaddon.py`, tooling and docs
  (these never ship). `pyproject.toml` sets `pythonpath`/`mypy_path` to `src`, so imports
  resolve as `ai_field_filler.*`.

## Commands (always via `uv`)

```sh
uv sync --group dev                       # install dev deps
uv run pytest                             # all tests (pythonpath=src)
uv run pytest tests/test_http.py -v       # one file
uv run ruff format && uv run ruff check   # format, then lint (--fix to auto-apply)
uv run mypy --package ai_field_filler     # non-strict type check (mypy_path=src)
python build_ankiaddon.py [--check]       # build the .ankiaddon (--check = dry run)
```

`make check` runs lint + typecheck + test together.

## Definition of done

`uv run ruff format`, `uv run ruff check`, `uv run mypy --package ai_field_filler`, and
`uv run pytest` all clean, at every commit. Line length 100. Adding a `# noqa` or
`# type: ignore` needs explicit human approval — fix the underlying issue first.

## Live testing in Anki

This repo is developed as a normal project; the addon is exposed to Anki by symlinking only
the package into the profile: `addons21/ai_field_filler → <repo>/src/ai_field_filler`. Edits
under `src/` are live on Anki restart. Anki writes the user's live config to
`src/ai_field_filler/meta.json` (gitignored).

## Boundaries

- ✅ **Always**: run the full DoD before committing; add/adjust tests with each behavior change.
- ⚠️ **Ask first**: adding any dependency; changing the provider interface (`providers/base.py`);
  changing `config.json` defaults or the config schema.
- 🚫 **Never**: introduce a compiled dependency; use 3.10+ syntax; commit secrets/API keys;
  add tool attribution to commits (see `.claude/rules/git-conventions.md`).

## Deeper docs & rules (read when relevant)

- Python conventions — `.claude/rules/python.md`
- Git & commit conventions — `.claude/rules/git-conventions.md`
- Provider layer internals — `src/ai_field_filler/providers/CLAUDE.md`
- Test harness (fixtures, singleton reset) — `tests/CLAUDE.md`
- Testing guide — `TESTING.md` · Config reference — `src/ai_field_filler/config.md`
