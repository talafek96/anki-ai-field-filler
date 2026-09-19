<!-- Loads only when a file in tests/ is touched. Don't restate root conventions. -->

# Tests

Governs `tests/` only. `pytest`; run via `uv run pytest tests/ -v` (one file:
`uv run pytest tests/test_http.py -v`).

## Fixtures & the singleton trap

- Shared fixtures live in `conftest.py`: `provider_config`, `filler`, `mock_mw`. Reuse them;
  don't rebuild that setup per test.
- **`ConfigManager` is a singleton.** A test that constructs a fresh one MUST first reset
  `ConfigManager._instance = None`, or it silently reuses another test's state. This is the
  most common source of order-dependent test failures here.

## Conventions

- `E501` (line length) is ignored under `tests/` — long inline fixtures/URLs are fine.
- Mock the network; never hit a real provider endpoint or require an API key to run the suite.
- Add or adjust a test with every behavior change (definition of done includes `uv run pytest`).
