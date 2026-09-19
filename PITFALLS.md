# Pitfalls

## OpenAI image API: `response_format` rejected for dall-e-3

- **Symptom:** `OpenAI API error 400: Unknown parameter: 'response_format'` when generating images with `dall-e-3`.
- **Cause:** OpenAI unified the image generation API; `response_format` is no longer accepted (was previously valid for DALL-E models but not for `gpt-image-*`).
- **Fix:** Added fallback in `OpenAIImageProvider.generate_image()` — if the API rejects `response_format`, retry with `output_format` instead.
- **Commit:** f64d3a5

## Newer models: the 2026-09 audit

Every model returned by all three providers' model-list endpoints was called
through the addon's own provider code. Baseline: **57 of 124 text models worked**.
After the fixes below: **90 of 96** (the remaining 6 are deprecated server-side
and now produce an actionable error instead of raw JSON).

The general lesson: **capability is negotiated at runtime, never assumed from the
model id.** Providers add models faster than any hard-coded list can track, so
each quirk below is detected from the API's own error message and cached per
model id for the session.

### `temperature` is rejected by reasoning models — 23 models

- **Symptom:** `Unsupported value: 'temperature' does not support 0.7 with this
  model. Only the default (1) value is supported.` Also appears as
  `Unsupported parameter: 'temperature' is not supported with this model.` and
  `Model incompatible request argument supplied: temperature`.
- **Hit:** `gpt-5`, `gpt-5-mini`, `gpt-5-nano`, `gpt-5.5`, `gpt-5.6-*`,
  `gpt-6-astra`, `o1`, `o3`, `o3-mini`, `o4-mini`, `chat-latest`.
- **Cause:** The addon sent a hard-coded `temperature: 0.7` on every request.
  This was the single largest cause of "new models don't work".
- **Fix:** On a temperature error, drop the parameter and retry; remember the
  model in `_MODEL_QUIRKS` so it is only paid once per session.

### `*-pro` models are not served by `/chat/completions` — 17 models

- **Symptom:** `404 ... This is not a chat model and thus not supported in the
  v1/chat/completions endpoint` or `This model is only supported in v1/responses`.
- **Hit:** `gpt-5-pro`, `gpt-5.2-pro`, `gpt-5.4-pro`, `gpt-5.5-pro`, `o1-pro`,
  `o3-pro`, `gpt-live-1`.
- **Fix:** `OpenAITextProvider._generate_responses()` retries against
  `/v1/responses` with `instructions`/`input`/`max_output_tokens`. Note the
  response shape differs: walk `output[]` for `message` items and collect
  `output_text` parts — reasoning items are interleaved, so `output[0]` is wrong.

### Anthropic: thinking blocks precede the answer

- **Symptom:** `Unexpected Anthropic response format: 'text'` on `claude-fable-5`.
- **Cause:** `result["content"][0]["text"]` assumed the first content block is
  text. With extended thinking, block 0 is a `thinking` block, so the newest
  models were exactly the ones that broke.
- **Fix:** Join every block whose `type` is `text`; ignore the rest.

### Google: `parts[0]` can be a reasoning part

- Gemini 3.x thinking models emit `{"thought": true}` parts before the answer.
- **Fix:** `_join_text_parts()` skips parts flagged `thought`.

### Google: Gemma rejects `system_instruction`

- **Symptom:** `400 Developer instruction is not enabled for models/X`. Worse,
  `gemma-4-*` returned a *wrong answer* rather than an error — it echoed the
  system prompt back as commentary instead of obeying it.
- **Fix:** On that error, fold the system prompt into the user turn and retry.

### Model lists advertise models that cannot be used

The `/models` endpoints are catalogues, not capability manifests:

- **Anthropic** returned all 11 Claude models for `tts` and `image` because
  `_fetch_anthropic_models` ignored the `capability` argument. The settings UI
  hid the rows anyway via `PROVIDER_CAPABILITIES`, so this was latent rather
  than user-visible — but the function's contract was wrong for any other
  caller. It now returns `[]` for non-text capabilities.
- **OpenAI** listed completions-only models (`davinci-002`, `babbage-002`,
  `*-instruct`) and endpoint-specific ones (`deep-research`, `search-preview`,
  `gpt-live`) as chat models. Added to `_OPENAI_SKIP_SIGNALS`.
- **Google** listed music (`lyria-*`), robotics, speech-to-text, computer-use,
  and Interactions-API-only models as text models. `lyria-*` failed with
  `PROHIBITED_CONTENT`, which looks alarming but just means "wrong endpoint".
- Deprecated-but-still-listed models (`gpt-5.1-chat-latest`, `gemini-2.5-pro`)
  cannot be detected statically — they now raise a clear "pick a current model"
  error instead of a raw 404 body.

### OpenRouter absorbs most of this, and is the hedge against it recurring

Measured against the same audit, OpenRouter is the most resilient option we
have, because it normalises requests per model **server-side**:

- `openai/gpt-6-astra` accepts `temperature` through OpenRouter, while the
  native OpenAI API rejects it. The same holds for the `*-pro` models, which
  need `/v1/responses` natively but work over plain chat/completions here.
- Its `/models` endpoint is the only one of the four that publishes real
  capability metadata (`architecture.output_modalities`,
  `supported_parameters`), so `_fetch_openrouter_models` classifies instead
  of guessing from the model id. 89 of its text models declare no
  `temperature` support — information no other provider exposes.

It has its own failure modes: models are listed whose upstream providers
are all offline, returning "No endpoints found", which
`OpenRouterTextProvider.generate` translates into a "pick a different
model" message; and `:batch` variants are listed but served only by
`/api/v1/batches`, so they are filtered out.

### OpenRouter speech is streaming-only

There is no `/audio/speech` endpoint and no dedicated TTS models — of 447
models only `openai/gpt-audio` and `openai/gpt-audio-mini` produce speech
(the other audio-output models are Lyria *music* generation). Speech comes
from a chat completion with an audio modality, and **only when `stream` is
set**: a normal request is refused with "Audio output requires stream:
true". That is why `providers/http.py` grew `http_post_sse`.

Two more constraints found by testing, not documented anywhere obvious:

- **`pcm16` is the only format the streaming path accepts.** `wav`, `mp3`
  and `opus` are all rejected with a 400. The result is raw 24 kHz mono
  PCM, so `MediaHandler` adds the WAV header exactly as it does for Google.
- **The voice is validated and cannot be blank.** An empty or unknown
  voice is a 400. The accepted list, taken from the API's own error
  message, is alloy, ash, ballad, cedar, coral, echo, fable, marin, nova,
  onyx, sage, shimmer, verse.

Vendoring a unified-API library (LiteLLM, any-llm, aisuite) was rejected:
all need compiled dependencies (`tokenizers`, `pydantic-core`) and Python
≥3.10, and an `.ankiaddon` can only bundle pure-Python code. LiteLLM also
requires `<3.15`, while this addon targets 3.9+.

### Gemini image models return JPEG, not PNG

- **Symptom:** none visible at first — the file is written and usually renders.
- **Cause:** `save_image()` hard-coded a `.png` extension, but 6 of 7 Gemini
  image models (including `nano-banana-pro-preview`) return JPEG bytes
  (`ff d8 ff e0`). OpenAI's return real PNG (`89 50 4e 47`).
- **Fix:** `MediaHandler._sniff_image_ext()` picks the extension from the magic
  bytes (png/jpg/webp/gif). Mirrors what `save_audio()` already did for PCM.
