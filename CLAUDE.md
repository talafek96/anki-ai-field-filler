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

`git log` is the history. Deeper design notes: `README.md`, `TESTING.md`, `config.md`.

## Two constraints that shape every decision here

1. **Pure-Python only.** An `.ankiaddon` bundles source, not wheels — it cannot ship
   compiled dependencies. This is why unified-LLM libraries (LiteLLM, any-llm, aisuite)
   were rejected; see PITFALLS. Any new dependency must be pure-Python **and** justified.
2. **Python 3.9 is the floor** (`requires-python = ">=3.9"`, CI runs 3.9/3.12/3.13). Do not
   use 3.10+ syntax: no `match`, no `X | Y` unions in runtime-evaluated annotations
   (use `Optional[...]`/`Union[...]`), no `from __future__` workarounds assumed present.

A third, learned the hard way: **provider capability is negotiated at runtime, never assumed
from a model id.** New models appear faster than any hard-coded list; detect quirks from the
API's own error and cache per model id. Detail lives in `providers/CLAUDE.md` + PITFALLS.

## Stack & layout

- **Stack:** Python 3.9+, PyQt (`aqt`/`anki`), `uv` for env/deps, `ruff` + `mypy`, `pytest`.
- **Layout:** provider code in `providers/`, Qt dialogs/tabs in `ui/`, tests in `tests/`
  (each has its own `CLAUDE.md`). Orchestration in `field_filler.py`; config dataclasses +
  singleton in `config_manager.py`; media writes in `media_handler.py`; Anki entry points in
  `__init__.py`, `editor_hooks.py`, `browser_hooks.py`; packaging in `build_ankiaddon.py`.

## Commands (always via `uv`)

```sh
uv sync --group dev                       # install dev deps + editable package
uv run pytest tests/ -v                   # all tests
uv run pytest tests/test_http.py -v       # one file
uv run ruff format && uv run ruff check   # format, then lint (--fix to auto-apply)
uv run mypy .                             # non-strict type check
python build_ankiaddon.py [--check]       # build the .ankiaddon (--check = dry run)
```

## Definition of done

`uv run ruff format`, `uv run ruff check`, `uv run mypy .`, and `uv run pytest` all clean,
at every commit. Line length 100. Adding a `# noqa` or `# type: ignore` needs explicit
human approval — fix the underlying issue first.

## Config: two files, don't confuse them

- **`config.json`** — the defaults shipped with the addon (check this when debugging what
  a user sees out of the box).
- **`meta.json`** — the user's live config, managed by Anki's addon manager; may differ
  from the defaults.

## Boundaries

- ✅ **Always**: run the full DoD before committing; add/adjust tests with each behavior change.
- ⚠️ **Ask first**: adding any dependency; changing the provider interface (`providers/base.py`);
  changing `config.json` defaults or the config schema.
- 🚫 **Never**: introduce a compiled dependency; use 3.10+ syntax; commit secrets/API keys;
  add tool attribution to commits (see `.claude/rules/git-conventions.md`).

## Deeper docs & rules (read when relevant)

- Python conventions — `.claude/rules/python.md`
- Git & commit conventions — `.claude/rules/git-conventions.md`
- Provider layer internals — `providers/CLAUDE.md`
- Test harness (fixtures, singleton reset) — `tests/CLAUDE.md`
- Testing guide — `TESTING.md` · Config reference — `config.md`
