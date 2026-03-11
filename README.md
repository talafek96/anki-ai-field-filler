# AI Field Filler

An Anki addon that uses AI (LLM-based) to intelligently auto-fill blank note fields. It considers already-filled fields, configurable per-field instructions, and optional user prompts to generate appropriate content — including text, audio (TTS), and images.

## Features

- **Multi-provider AI support** — OpenAI, Anthropic (Claude), Google (Gemini), and any OpenAI-compatible API
- **Smart field filling** — The AI decides what content type fits each field (text, audio, image) and leaves irrelevant fields empty
- **Per-field instructions** — Configure what each field should contain per note type, giving the AI rich context
- **Flexible activation** — Fill all blank fields at once or target specific fields
- **Multiple activation methods**:
  - Editor toolbar buttons ("AI Fill All", "AI Fill")
  - Right-click context menu on fields
  - Configurable keyboard shortcuts
- **Comfortable settings UI** — Tabbed settings dialog with provider config, note type instructions, and general settings
- **Inline configuration** — Right-click any field to quickly set its AI instructions
- **Text-to-speech** — Automatically generates audio files for audio fields (OpenAI TTS)
- **Image generation** — Automatically generates images for image fields (OpenAI DALL-E)

## Installation

### From source

1. Clone or copy the `ai_field_filler` folder into your Anki addons directory:
   - **Windows**: `%APPDATA%\Anki2\addons21\`
   - **macOS**: `~/Library/Application Support/Anki2/addons21/`
   - **Linux**: `~/.local/share/Anki2/addons21/`

2. Restart Anki

3. Configure your AI provider credentials via **Tools → AI Field Filler → Settings...**

## Configuration

### Quick Start

1. Open **Tools → AI Field Filler → Settings...**
2. Go to the **AI Providers** tab
3. Enter your API key for your preferred provider (OpenAI, Anthropic, or Google)
4. Click **Test Connection** to verify
5. Go to the **Note Types** tab
6. Select a note type and describe what each field should contain
7. Click **OK** to save

### AI Providers Tab

Configure credentials and models for each supported provider:

| Provider | Text | TTS | Image | Notes |
|----------|------|-----|-------|-------|
| OpenAI | Yes | Yes | Yes | Also works with Azure OpenAI and other compatible APIs |
| Anthropic | Yes | No | No | Claude models |
| Google | Yes | No | No | Gemini models |

You can select which provider to use for each capability (text generation, TTS, image generation) independently. For example, use Anthropic for text but OpenAI for TTS/images.

**Using OpenAI-compatible APIs**: Change the API URL to point to your endpoint (e.g., Azure OpenAI, local LLM server, or any OpenAI-compatible API).

### Note Types Tab

For each note type, describe what each field should contain. This gives the AI rich context for generating appropriate content.

For each field you can configure:
- **Instruction**: A description of what the field should contain (e.g., "English definition of the word", "Example sentence using this grammar point")
- **Content Type**: `Auto` (let AI decide), `Text`, `Audio`, or `Image`
- **Include in auto-fill**: Whether this field is included when using "Fill All Blank Fields"

### General Tab

- **Keyboard shortcuts**: Customize shortcuts for fill actions (default: `Ctrl+Shift+G` for all, `Ctrl+Shift+F` for current field)
- **Show confirmation dialog**: When enabled, shows a dialog to review and customize each fill operation
- **Default user prompt**: Additional instructions included with every AI request

## Usage

### Fill All Blank Fields

Fill all empty fields in the current note at once:
- Click the **"AI Fill All"** button in the editor toolbar
- Or right-click in the editor → **"AI: Fill all blank fields"**
- Or press `Ctrl+Shift+G` (configurable)

### Fill a Specific Field

Fill just the field you're working on:
- Click the **"AI Fill"** button in the editor toolbar
- Or right-click on a field → **"AI: Fill '{field name}'"**
- Or press `Ctrl+Shift+F` (configurable)

### Quick Field Configuration

Right-click on any field in the editor → **"AI: Configure instructions for '{field name}'..."** to quickly set or edit the AI instruction for that field without opening the full settings dialog.

### Fill Dialog

When the confirmation dialog is enabled (default), you'll see:
- Checkboxes for each field (pre-selected based on which are blank and auto-fill settings)
- An optional text area for additional one-time instructions
- Select All / Deselect All buttons for convenience

## How It Works

1. When you trigger a fill action, the addon gathers:
   - All field names and their current values
   - Per-field instructions you've configured for this note type
   - Any additional user prompt
2. This context is sent to your configured AI provider
3. The AI returns structured content for each requested field
4. For text fields: content is inserted directly
5. For audio fields: text is sent to the TTS provider, audio is saved to Anki's media folder, and a `[sound:filename.mp3]` tag is inserted
6. For image fields: a generation prompt is sent to the image provider, the image is saved, and an `<img>` tag is inserted
7. Fields the AI deems irrelevant are left empty

## File Structure

```
ai_field_filler/
├── __init__.py              # Addon entry point
├── config.json              # Default configuration
├── config.md                # Configuration documentation
├── config_manager.py        # Typed config wrapper (singleton)
├── field_filler.py          # Core orchestrator
├── media_handler.py         # Audio/image media management
├── editor_hooks.py          # Editor toolbar + context menu
├── providers/
│   ├── __init__.py          # Provider factory
│   ├── base.py              # Abstract base classes
│   ├── openai_provider.py   # OpenAI (text + TTS + image)
│   ├── anthropic_provider.py # Anthropic (text)
│   └── google_provider.py   # Google Gemini (text)
└── ui/
    ├── __init__.py
    ├── settings_dialog.py         # Main tabbed settings dialog
    ├── provider_settings_tab.py   # Provider credentials tab
    ├── note_type_settings_tab.py  # Per-field instructions tab
    ├── general_settings_tab.py    # General settings tab
    ├── fill_dialog.py             # Fill activation dialog
    └── field_instruction_dialog.py # Quick field instruction editor
```

## Requirements

- Anki 2.1.50 or later (Qt6 recommended, Qt5 supported)
- An API key for at least one supported AI provider
- Internet connection for AI API calls

## Troubleshooting

### "Connection error" when testing provider
- Verify your API key is correct
- Check that the API URL is correct (default URLs work for most users)
- Ensure you have an active internet connection
- If behind a proxy, Anki may need proxy configuration

### Fields not being filled
- Make sure the AI provider is configured and the connection test passes
- Check that target fields are blank (the addon won't overwrite existing content)
- Verify field instructions are set up in the Note Types tab
- Check the "Include in auto-fill" checkbox for fields you want auto-filled

### Audio/Image not generating
- Ensure TTS/Image is not set to "Disabled" in the Active Providers section
- For OpenAI: verify the TTS Model and Image Model fields are filled in
- Check that the field's Content Type is set to "Audio" or "Image" (or "Auto")

## License

MIT License. See LICENSE file for details.

## Contributing

Contributions are welcome! Please open an issue or pull request on GitHub.
