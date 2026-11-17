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
| `tts_model` | Model for text-to-speech (OpenAI / Google / OpenRouter) |
| `tts_voice` | Voice for TTS (OpenAI / Google / OpenRouter) |
| `image_model` | Model for image generation (OpenAI / Google / OpenRouter) |
| `tts_api_url` | Optional separate server for text-to-speech. Empty: use `api_url` |
| `tts_api_key` | Key for `tts_api_url`. Empty: use `api_key` |
| `image_api_url` | Optional separate server for images. Empty: use `api_url` |
| `image_api_key` | Key for `image_api_url`. Empty: use `api_key` |

Set a separate server when speech or images come from somewhere other than
`api_url`, for example a local OpenAI-compatible text-to-speech server. In the
Settings dialog, tick **Use a different server for speech** (or **images**).

## `active_providers`

Which provider to use for each capability:

| Key | Values | Description |
|-----|--------|-------------|
| `text` | `openai`, `anthropic`, `google`, `openrouter` | Provider for text generation |
| `tts` | `openai`, `google`, `openrouter`, `disabled` | Provider for text-to-speech |
| `image` | `openai`, `google`, `openrouter`, `disabled` | Provider for image generation |

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
| `dev_mode` | Adds a "Developer Tools" entry to the addon menu. The dialog is always reachable with `Ctrl+Shift+Alt+D` regardless of this setting. |
