# AI Field Filler - Development Notes

## Dev Setup (uv)

```bash
# Install uv (if not already installed)
pip install uv

# Install dev dependencies + package in editable mode
uv sync --group dev

# Run tests
uv run pytest tests/ -v

# Run linters
uv run ruff check .
uv run ruff format --check .
uv run mypy .

# Auto-fix lint issues
uv run ruff check . --fix
uv run ruff format .

# Build .ankiaddon package
python build_ankiaddon.py
python build_ankiaddon.py --check  # dry-run
```

## Project Structure

- `providers/http.py` — Shared HTTP helpers (all providers use these)
- `providers/base.py` — Abstract base classes and `ProviderError`
- `providers/{openai,anthropic,google}_provider.py` — Provider implementations
- `providers/__init__.py` — Factory functions, model fetching, model classification
- `config_manager.py` — Config dataclasses (`ProviderConfig`, `FieldInstruction`, `GeneralSettings`, `FIELD_TYPES`) and singleton `ConfigManager`
- `field_filler.py` — Core orchestrator (prompt building, AI calls, response parsing)
- `media_handler.py` — Saves generated audio/images to Anki media folder
- `editor_hooks.py` — Editor toolbar buttons and context menu
- `ui/` — Qt settings dialogs and tabs
- `ui/__init__.py` — Shared UI helpers (`create_field_type_combo`, `create_auto_fill_checkbox`)

## Conventions

- **No in-function imports.** All imports at the top of the file. Only exceptions:
  - `providers/__init__.py` factory functions use lazy imports to avoid circular deps
  - `__init__.py` startup uses guarded imports for Anki modules
- All HTTP requests go through `providers/http.py` helpers (`http_post_json`, `http_post_raw`, `http_get_json`)
- Use `ProviderConfig.base_url` instead of `api_url.rstrip("/")`
- Use `FIELD_TYPES` from `config_manager` instead of defining inline lists
- Use `create_field_type_combo()` / `create_auto_fill_checkbox()` from `ui/` for consistent UI widgets
- Tests use shared fixtures from `conftest.py`: `provider_config`, `filler`, `mock_mw`
- ConfigManager is a singleton — tests must reset `ConfigManager._instance = None` before creating new instances

## CI

GitHub Actions runs on every push/PR to `main`:
- **Lint**: ruff check, ruff format, mypy (Python 3.12)
- **Test**: pytest on Python 3.9, 3.12, 3.13

## Config Files

- `config.json` in the repo root is the **defaults** file shipped with the addon
- The user's actual running config is managed by Anki's addon manager (stored in `meta.json`) and may differ from `config.json`
- When debugging user-reported issues, check `config.json` to see what defaults are in play

## Git

- Do NOT include "Generated with Devin" or "Co-Authored-By: Devin" in commit messages
