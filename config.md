# AI Field Filler - Configuration

This is the raw JSON configuration for AI Field Filler. For a friendlier
interface, use **Tools → AI Field Filler → Settings...** from the Anki menu.

---

## `providers`

API credentials and model settings for each supported AI provider.

| Key | Description |
|-----|-------------|
| `api_url` | Base URL for the provider's API |
| `api_key` | Your API key (keep this secret!) |
| `text_model` | Model name for text generation |
| `max_tokens` | Maximum tokens in AI responses |
| `tts_model` | Model for text-to-speech (OpenAI only) |
| `tts_voice` | Voice for TTS — alloy, echo, fable, onyx, nova, shimmer (OpenAI only) |
| `image_model` | Model for image generation (OpenAI only) |

## `active_providers`

Which provider to use for each capability:

| Key | Values | Description |
|-----|--------|-------------|
| `text` | `openai`, `anthropic`, `google` | Provider for text generation |
| `tts` | `openai`, `disabled` | Provider for text-to-speech |
| `image` | `openai`, `disabled` | Provider for image generation |

## `note_type_field_instructions`

Per-note-type, per-field AI instructions. Populated via the Settings dialog.

Example:
```json
{
    "Japanese (Recognition)": {
        "Meaning": {
            "instruction": "English definition of the Expression field",
            "field_type": "text",
            "auto_fill": true
        }
    }
}
```

- `instruction`: Description of what the field should contain
- `field_type`: `auto`, `text`, `audio`, or `image`
- `auto_fill`: Whether to include in "Fill All Blank Fields"

## `general`

| Key | Description |
|-----|-------------|
| `fill_all_shortcut` | Keyboard shortcut for filling all blank fields |
| `fill_field_shortcut` | Keyboard shortcut for filling the current field |
| `default_user_prompt` | Default additional prompt included with every AI request |
| `show_fill_dialog` | Show a confirmation dialog before filling fields |
