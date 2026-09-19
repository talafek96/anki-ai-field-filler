# AI Field Filler

An Anki addon that uses AI (LLM-based) to intelligently auto-fill blank note fields. It considers already-filled fields, configurable per-field instructions, and optional user prompts to generate appropriate content — including text, audio (TTS), and images.

## Features

- **Multi-provider AI support** — OpenAI, Anthropic (Claude), Google (Gemini / Nano Banana), OpenRouter (one key for every vendor), and any OpenAI-compatible API
- **Smart field filling** — The AI decides what content type fits each field (text, audio, image) and leaves irrelevant fields empty
- **Batch fill from browser** — Select multiple cards in the browser, fill all their blank fields in one go with a full review workflow (configure → progress → review diffs → apply)
- **Optional inline images** — For text fields, the AI can include a generated illustration when it would help the learner, appended below the text in the same field
- **Per-field instructions** — Configure what each field should contain per note type, giving the AI rich context
- **Flexible activation** — Fill all blank fields at once or target a specific field
- **Context-sensitive dialogs**:
  - **Fill All**: full dialog with field checkboxes (already-filled fields are disabled), optional prompt, select/deselect all
  - **Fill Field**: lightweight prompt-only dialog — just the field name and an optional instruction
- **Multiple activation methods**:
  - Editor toolbar buttons ("AI Fill All", "AI Fill")
  - Right-click context menu on fields
  - Right-click in the browser for batch fill
  - Configurable keyboard shortcuts
- **Dynamic model selection** — Model dropdowns with a refresh button that fetches available models from the provider's API, cached per provider
- **Settings export/import** — Export all settings to a portable file for backup or transfer between computers, with optional password-based API key encryption
- **Comfortable settings UI** — Tabbed settings dialog with provider config, note type instructions, and general settings
- **Inline configuration** — Right-click any field to quickly set its AI instructions
- **Text-to-speech** — Automatically generates audio files for audio fields (OpenAI TTS, Google Gemini TTS); note context is passed to the TTS engine for accurate pronunciation
- **Image generation** — Automatically generates images for image fields (OpenAI DALL-E, Google Nano Banana)

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
4. Click the refresh icon next to a model dropdown to fetch available models
5. Click **Test Connection** to verify
6. Go to the **Note Types** tab
7. Select a note type and describe what each field should contain
8. Click **OK** to save

### AI Providers Tab

Configure credentials and models for each supported provider:

| Provider | Text | TTS | Image | Notes |
|----------|------|-----|-------|-------|
| OpenAI | Yes | Yes | Yes | Also works with Azure OpenAI and other compatible APIs |
| Anthropic | Yes | No | No | Claude models |
| Google | Yes | Yes | Yes | Gemini text, Nano Banana image gen, Gemini TTS |
| OpenRouter | Yes | Yes | Yes | One key for every vendor; normalises per-model parameter differences. Speech via streamed gpt-audio models |

- **Model dropdowns** are editable combo boxes with a refresh icon button that fetches available models from the provider's API. Fetched models are cached per provider — switching between providers restores each one's model list.
- **API key** field has a "Show" checkbox to toggle visibility.
- **Active provider** can be set independently for each capability (text, TTS, image). For example, use Anthropic for text but OpenAI for TTS and Google for images.
- **TTS voices** are pre-populated per provider (OpenAI: alloy, nova, shimmer, etc. / Google: Kore, Puck, Charon, etc.) but the field is editable for custom voices.

**Using OpenAI-compatible APIs**: Change the API URL to point to your endpoint (e.g., Azure OpenAI, local LLM server, or any OpenAI-compatible API).

### Note Types Tab

For each note type, describe what each field should contain. This gives the AI rich context for generating appropriate content.

For each field you can configure:
- **Instruction**: A description of what the field should contain (e.g., "English definition of the word", "Example sentence using this grammar point")
- **Content Type**: `Auto` (let AI decide), `Text`, `Audio`, or `Image`
- **Include in auto-fill**: Whether this field is included when using "Fill All Blank Fields"

### General Tab

- **Keyboard shortcuts**: Customize shortcuts for fill actions (default: `Ctrl+Shift+G` for all, `Ctrl+Shift+F` for current field)
- **Show confirmation dialog**: When enabled, shows a dialog before filling (full field selection for Fill All, prompt-only for Fill Field)
- **Default user prompt**: Additional instructions included with every AI request

## Usage

### Fill All Blank Fields

Fill all empty fields in the current note at once:
- Click the **"AI Fill All"** button in the editor toolbar
- Or right-click in the editor → **"AI: Fill all blank fields"**
- Or press `Ctrl+Shift+G` (configurable)

When the confirmation dialog is enabled, you'll see:
- Checkboxes for each blank field (already-filled fields are grayed out and disabled)
- An optional text area for additional one-time instructions
- Select All / Deselect All buttons for convenience

### Fill a Specific Field

Fill just the field you're working on:
- Click the **"AI Fill"** button in the editor toolbar
- Or right-click on a field → **"AI: Fill '{field name}'"**
- Or press `Ctrl+Shift+F` (configurable)

When the confirmation dialog is enabled, you'll see a lightweight popup with just the field name and an optional prompt — no field selection needed since you already chose the field.

### Quick Field Configuration

Right-click on any field in the editor → **"AI: Configure instructions for '{field name}'..."** to quickly set or edit the AI instruction for that field without opening the full settings dialog.

### Inline Images

For text fields, the AI can optionally include a generated illustration when it believes it would significantly help the learner. The image is appended below the text in the same field. To encourage this, add something like *"Include a helpful illustration when the concept is visual or concrete"* to the field's instruction.

### Batch Fill (Browser)

Fill blank fields across many notes at once from the card browser:

1. **Select cards** in the browser (all must share the same note type)
2. **Right-click → "AI: Batch fill blank fields (N cards)"**
3. **Configure** — Choose which fields to fill, add an optional prompt, and optionally enable dry-run mode
4. **Progress** — A progress dialog shows real-time status, ETA, and allows cancellation
5. **Review** — A side-by-side diff view shows before/after for every note. Each "After" panel is editable (WYSIWYG for HTML, inline audio preview with play buttons). You can accept or reject individual notes with checkboxes.
6. **Apply** — Only checked notes are written back to the collection. A summary dialog shows success/failure counts and total elapsed time.

### Export / Import Settings

Transfer your settings between computers or back them up:

1. Open **Tools → AI Field Filler → Settings...**
2. Click **"Export Settings..."** at the bottom of the dialog
3. Optionally enter a password to encrypt your API keys (leave blank to export without encryption)
4. Choose a save location — the file uses the `.aiff-settings` extension
5. To import: click **"Import Settings..."**, select a file, enter the password if encrypted, and confirm

Exported files include provider configs, active provider selections, all note type instructions, deck-specific overrides, and general settings. API keys are encrypted using PBKDF2-based key derivation when a password is provided.

## How It Works

1. When you trigger a fill action, the addon gathers:
   - All field names and their current values
   - Per-field instructions you've configured for this note type
   - Any additional user prompt
2. This context is sent to your configured AI provider as a structured prompt
3. The AI returns a JSON response with content for each requested field, including content type decisions
4. For text fields: content is converted to HTML (newlines → `<br>`) and inserted. If the AI included an `image_prompt`, the image is generated and appended below the text.
5. For audio fields: text is sent to the TTS provider (OpenAI or Google Gemini), audio is saved to Anki's media folder as MP3 or WAV (raw PCM from Google TTS is automatically wrapped in a WAV header), and a `[sound:filename]` tag is inserted
6. For image fields: a generation prompt is sent to the image provider (DALL-E or Nano Banana), the image is saved, and an `<img>` tag is inserted
7. Fields the AI deems irrelevant are left empty

## File Structure

The addon package lives in `src/ai_field_filler/`; its *contents* become the installed
`.ankiaddon`. Code is grouped by role, with tests and tooling kept above the package (they
never ship).

```
src/ai_field_filler/            # the addon package (contents = installed addon root)
├── __init__.py                 # Addon entry point
├── config.json                 # Default configuration
├── config.md                   # Configuration documentation (shown in Anki's config screen)
├── core/
│   ├── field_filler.py         # Core orchestrator (single + batch)
│   └── media_handler.py        # Audio/image media management
├── config/
│   ├── config_manager.py       # Typed config wrapper (singleton) + FIELD_TYPES
│   └── settings_io.py          # Settings export/import + encryption
├── providers/
│   ├── __init__.py             # Provider factory + model fetching
│   ├── base.py                 # Abstract base classes + ProviderError
│   ├── http.py                 # Shared HTTP request helpers (the only HTTP layer)
│   ├── openai_provider.py      # OpenAI (text + TTS + image)
│   ├── anthropic_provider.py   # Anthropic (text)
│   ├── google_provider.py      # Google Gemini (text + TTS + image)
│   └── openrouter_provider.py  # OpenRouter (text + TTS + image, all vendors)
├── ui/                         # Qt dialogs, tabs, and shared widget helpers
└── hooks/
    ├── editor_hooks.py         # Editor toolbar + context menu
    └── browser_hooks.py        # Browser batch fill integration

tests/                          # pytest suite (aqt mocked; never ships)
scripts/build_ankiaddon.py      # packages src/ai_field_filler/ into the .ankiaddon
pyproject.toml  Makefile  CLAUDE.md  .claude/   # tooling, agent context (never ship)
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
- For Google: verify the Image Model is set (e.g., `gemini-2.5-flash-image`)
- Check that the field's Content Type is set to "Audio" or "Image" (or "Auto")

### Model dropdown empty after fetching
- Make sure you've entered an API key before clicking the refresh icon
- The fetched models are cached per provider — switching providers shows that provider's cached models (or an empty list if not yet fetched)

## License

GPL-3.0 License. See [LICENSE](LICENSE) file for details.

## Contributing

Contributions are welcome! Please open an issue or pull request on GitHub.
