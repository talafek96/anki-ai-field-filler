# Manual test plan

Automated coverage lives in `tests/` (`make test`). This document covers what
mocks cannot: real API behaviour and Qt rendering.

Most of it is driven from the built-in **Developer Tools** dialog.

## Opening Developer Tools

- Press **`Ctrl+Shift+Alt+D`** anywhere in the main window, or
- set `"dev_mode": true` under `general` in the addon config to add
  **Tools → AI Field Filler → 🧪 Developer Tools...**

The dialog has a **Parameters** panel and five groups of buttons on the left,
with a scrollable log on the right. **Buttons in groups 2–5 spend real API
credits.**

### Parameters

Every run uses this panel rather than your saved settings, so a behaviour can
be tried against different setups without touching the real configuration:

| Field | Notes |
|-------|-------|
| Provider | `⟨use active providers⟩` follows your config; pick a specific one to override. TTS/image rows disable themselves for providers that lack the capability. |
| Text / Image / TTS model | Editable, with a refresh button that fetches from the selected provider. Blank means "provider default". |
| TTS voice | Pre-filled per provider, editable. |
| Max tokens | Drop this to ~50 to watch a reasoning model spend its whole budget thinking and return no text — the error should say so, not appear empty. |
| System / User / Image / TTS prompt | Edit to test your own prompts. |

*Reset parameters* restores the defaults.

### Stopping a run

**⏹ Stop** aborts between items. The request already in flight cannot be
cancelled — it completes and is billed, then the run stops. Closing the dialog
mid-run does the same and discards the result.

### Run all tests

Group 5 runs every non-interactive check in sequence, streaming into the log
and abortable at any point. The three error-dialog buttons are interactive and
are excluded; run those by hand.

---

## 1 · Error dialog

| Button | What to look for |
|--------|------------------|
| Plain message (no details) | Compact dialog. **No** "Show details" button — there is no payload to show. |
| API error + JSON details | One readable sentence at the top, *not* a JSON blob. "Show details" expands a monospace pane with pretty-printed JSON and a Copy button. |
| Oversized payload (scroll test) | ~200 lines of JSON. The dialog must stay a fixed size and scroll **inside** the details pane — it must not grow past the screen. Collapsing shrinks it back. |

Also check both themes: Anki *Preferences → Appearance → Theme*, light and dark.

## 2 · Model lists

| Button | What to look for |
|--------|------------------|
| List models (all providers) | Counts per provider × capability. **Anthropic tts/image must report 0** — Claude has no such models. OpenRouter tts reports 2 (`gpt-audio`, `gpt-audio-mini`); the Lyria music models must not appear there. |
| Show models filtered OUT | Every model the API returned that the dropdowns hide, e.g. `davinci-002`, `babbage-002`, `*-instruct`, `*-deep-research`, `lyria-*` (music), `*-robotics-*`, `*-transcribe`, `*-computer-use`, and OpenRouter's `*:batch` variants. Selecting any of these could only ever fail. |

OpenRouter's `:batch` models deserve a specific look: they are half-price
**asynchronous** jobs served only by `/api/v1/batches`, and a synchronous call
returns `404 This model is only available through the Batch API`. There are 74
of them, so they must not appear in the dropdown. Other suffixes (`:free`,
`:online`, `:thinking`, `:nitro`) are normal models and must still be listed.

Cross-check in the UI: **Settings → AI Providers**, click the refresh icon next
to *Text model*. The dropdown should contain none of the names listed above.

## 3 · Live calls (uses your **active** providers)

| Button | What to look for |
|--------|------------------|
| Test connection | `result: OK` for a working key. Break the key deliberately → the new error dialog appears with details, instead of the old plain message box. |
| Generate text | Reply is `'OK'`. |
| Generate image → report format | Reports magic bytes and the extension chosen. **Gemini 3.x must report JPEG → `.jpg`**; OpenAI reports PNG → `.png`. This is the bug where JPEG data was written to a `.png` filename. |
| Synthesize speech → report format | Google and OpenRouter return `raw/unknown (PCM?)` — expected; `MediaHandler` wraps it in a WAV header. OpenAI returns MP3. For OpenRouter, only `openai/gpt-audio` and `openai/gpt-audio-mini` are offered, the voice must be one of the 13 accepted names, and the request is streamed — a blank voice or a non-`pcm16` format is a 400. |

## 4 · Compatibility probe

Runs the models that used to fail, each exercising a different quirk.

| Provider | Model | Was failing because |
|----------|-------|---------------------|
| OpenAI | `gpt-5.5`, `gpt-6-astra`, `o3` | hard-coded `temperature: 0.7` |
| OpenAI | `gpt-5.4-pro`, `o1-pro` | only served by `/v1/responses` |
| Anthropic | `claude-fable-5` | thinking block ahead of the text block |
| Google | `gemma-4-31b-it` | rejects `system_instruction` |
| Google | `gemini-3.1-pro-preview` | reasoning parts before the answer |
| OpenRouter | `openai/gpt-6-astra`, `openai/gpt-5.4-pro` | normalised server-side, so they just work |

Two entries are **expected to fail**, and the point is *how*:
`gemini-2.5-pro` (retired by Google) and `nvidia/nemotron-nano-9b-v2` (no live
OpenRouter endpoint) must produce a readable sentence telling you to pick
another model — not a raw JSON body.

---

## End-to-end, outside the dev dialog

1. **Fill a field.** Open any note, put the cursor in a blank field, press
   `Ctrl+Shift+F`. Try it with a model that used to fail, e.g. set the OpenAI
   text model to `gpt-5.5` or `gpt-6-astra`.
2. **Image field.** Fill a field whose content type is `image` using a Gemini
   image model. Then run *Tools → Check Media*: the generated file should be
   `.jpg` and report no problems.
3. **Audio field.** Fill an `audio` field with Google TTS and confirm the
   `[sound:...]` tag plays.
4. **OpenRouter.** Settings → AI Providers → *OpenRouter (all vendors)*, paste
   a key, refresh the model list, set it active for text, and fill a field.
   Then set it active for TTS as well and fill an `audio` field: speech is
   streamed, so this exercises `http_post_sse` end to end. The saved file
   must be a playable `.wav` (24 kHz mono).
5. **Batch fill.** Select several notes of one type in the browser →
   right-click → batch fill, then regenerate a field in the review dialog. A
   failure there should open the new error dialog.

## Automated checks

```bash
make check    # lint + typecheck + test (390 tests)
python build_ankiaddon.py --check   # confirm new files are packaged
```

Tests import the package as `ai_field_filler` from `src/`; `pyproject.toml` sets
`pythonpath`/`mypy_path` to `src`, so `uv run pytest` and `uv run mypy --package
ai_field_filler` resolve it with no symlink or `PYTHONPATH` setup.
