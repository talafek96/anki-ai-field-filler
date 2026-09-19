---
paths:
  - "**/*.py"
---

# Python Conventions

Language-specific *how* for this addon. The project-wide constraints (pure-Python only,
Python 3.9 floor, runtime capability negotiation) are in the root `CLAUDE.md`; on conflict,
the root file wins.

## Tooling — always through `uv`

- **Never invoke the OS Python.** Every action goes through `uv`: `uv run python …`,
  `uv run ruff …`, `uv run mypy .`, `uv run pytest`. No bare `python`, `python3`, or `pip`.
- Config lives in `pyproject.toml`. Line length **100**. `ruff` owns formatting and import
  sorting; code MUST be clean under `uv run ruff check` before a change is done.
- `uv run mypy .` runs **non-strict** by decision — do not enable `strict`. `ui/*` and
  `editor_hooks` are excluded/ignored in mypy config (Qt typing); don't "fix" that by
  loosening the rest.

## Compatibility floor — Python 3.9

The addon runs on Anki's bundled interpreter, CI covers 3.9/3.12/3.13, so **3.9 is the
floor**:

- No `match` statements.
- No `X | Y` unions in annotations evaluated at runtime — use `Optional[...]` / `Union[...]`
  from `typing`. (`list[int]`-style builtins in annotations are fine only where not evaluated.)
- Prefer `typing` constructs that work on 3.9 over 3.10+ conveniences.

## Imports — all at the top, no exceptions in normal code

- **All imports and module-level constants/globals at the top of the file**, right after the
  module docstring. **No imports inside functions or other scopes.** If a heavy or circular
  import tempts you into a function, fix the dependency instead.
- The only sanctioned exceptions: `providers/__init__.py` factory functions use lazy imports
  to avoid circular deps; `__init__.py` startup uses guarded imports for Anki modules.
- `from aqt.qt import *` is the Anki convention and is why `F403`/`F405` are ignored — keep
  it; don't enumerate Qt imports by hand.

## Reuse — one way to do a thing

- **All HTTP goes through `providers/http.py`** helpers (`http_post_json`, `http_post_raw`,
  `http_get_json`, `http_post_sse`). Never hand-roll a request or re-implement retry/error
  handling.
- Use `ProviderConfig.base_url`, not `api_url.rstrip("/")`.
- Use `FIELD_TYPES` from `config_manager`, not an inline list of field types.
- Use `create_field_type_combo()` / `create_auto_fill_checkbox()` from `ui/` for those widgets.
- Prefer standard-library primitives and existing helpers before writing new ones. Do not add
  a library when an existing dependency or the stdlib covers the need.

## Structure & style

- Small, single-purpose functions; validate arguments and return early.
- `pathlib` over manual path joining; f-strings over `%`/`.format`.
- **Type hints required** on function/method signatures. Comment **why**, not **what**.
- Fail fast on broken invariants; raise rather than limp on. Catch narrowly, only where you
  can genuinely recover. Provider errors surface as `ProviderError` with an actionable message.

## Tests

- Definition of done for any Python change: `uv run ruff format`, `uv run ruff check`,
  `uv run mypy .`, `uv run pytest` all clean.
- Prefer shared `pytest` fixtures over copy-paste setup (see `tests/CLAUDE.md`).
