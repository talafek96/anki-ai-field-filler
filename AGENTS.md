# AI Field Filler - Development Notes

## Build & Test

```bash
# Run all tests (from addons21/ directory)
python -m pytest ai_field_filler/tests/ -v

# Run a specific test file
python -m pytest ai_field_filler/tests/test_config.py -v
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
