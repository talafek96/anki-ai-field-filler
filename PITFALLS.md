# Pitfalls

## OpenAI image API: `response_format` rejected for dall-e-3

- **Symptom:** `OpenAI API error 400: Unknown parameter: 'response_format'` when generating images with `dall-e-3`.
- **Cause:** OpenAI unified the image generation API; `response_format` is no longer accepted (was previously valid for DALL-E models but not for `gpt-image-*`).
- **Fix:** Added fallback in `OpenAIImageProvider.generate_image()` — if the API rejects `response_format`, retry with `output_format` instead.
- **Commit:** f64d3a5
