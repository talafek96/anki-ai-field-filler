# Handoff

Session-to-session working state for AI Field Filler. Read this and `PITFALLS.md` on spawn.
Update it at milestones; keep it current to reality (`git log` is the authoritative history).

## Current state

Prior product work (on `main`): OpenRouter streaming speech synthesis, a full
model-capability audit across all four providers, Developer Tools made configurable/abortable.
See `git log` and `PITFALLS.md` for details.

On branch `usr/tal-afek/claude-onboarding` (not yet merged):
- **Claude Code onboarding** — root + nested `CLAUDE.md`, `.claude/rules/`, `.claude/commands/`,
  vendored `.claude/skills/`, `.claude/constitution.md` (@-imported into CLAUDE.md), this file.
- **`src/` refactor** — the addon package moved to `src/ai_field_filler/` and split into
  `core/`, `config/`, `providers/`, `ui/`, `hooks/`. `scripts/build_ankiaddon.py`, CI, and
  `pyproject.toml` (`pythonpath`/`mypy_path=src`) updated; folder-name symlink hack removed.
- **Static convention enforcement** — ruff now checks no-in-function-imports, signature type
  hints, naming, HTTP-only-through-`http.py`, and no blanket suppressions; violations fixed.

**Dev install:** the repo now lives at `~/projects/anki-ai-field-filler`; Anki loads it via
`addons21/ai_field_filler → src/ai_field_filler` (symlink). Restart Anki to pick it up.
Full gate is green: `make check` → ruff + mypy + 390 tests.

## In flight

_Nothing in flight. Add work-in-progress here as it starts._

## Next steps

_None queued. Add ordered, independently-verifiable next tasks here at session close._
