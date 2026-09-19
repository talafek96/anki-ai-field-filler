<!-- Loads only when a file in providers/ is touched. Don't restate root conventions. -->

# Provider layer

Governs `providers/` only. Each provider adapts one vendor's API to the common interface;
the golden rule is **capability is negotiated at runtime, never assumed from a model id.**
New models ship faster than any hard-coded list, so quirks are detected from the API's own
error message and cached per model id for the session. Full case history is in `../PITFALLS.md`
— read it before touching provider behavior.

## Files

- `base.py` — abstract base classes + `ProviderError` (the one error type callers see).
- `http.py` — the **only** place HTTP happens: `http_post_json`, `http_post_raw`,
  `http_get_json`, `http_post_sse`. Add transport concerns here, not in a provider.
- `{openai,anthropic,google}_provider.py` — vendor implementations.
- `openrouter_provider.py` — **subclasses the OpenAI one** (OpenRouter is OpenAI-compatible)
  and is the most resilient path: it normalizes params server-side and its `/models` endpoint
  is the only one publishing real capability metadata.
- `__init__.py` — factory functions (lazy imports here are sanctioned to break cycles), model
  fetching, and model classification.

## Invariants when adding or changing a provider

- Route every request through `http.py`; never build a request inline.
- On a parameter/endpoint rejection, **detect from the error, drop/retry, and cache the quirk**
  per model id (the `_MODEL_QUIRKS` pattern) — don't hard-code model lists. Known live cases:
  reasoning models reject `temperature`; `*-pro` models need `/v1/responses` not
  `/chat/completions`; thinking models put non-text blocks before the answer.
- `/models` endpoints are catalogues, not capability manifests — classify/filter, don't trust.
- Translate every failure into a `ProviderError` with a message that tells the user what to do
  (e.g. "pick a current model"), never a raw JSON body.
- Any behavior you discover by testing an API goes into `../PITFALLS.md` in the same change.
