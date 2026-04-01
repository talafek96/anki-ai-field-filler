# AI Filler for Anki

An Anki add-on that uses LLMs (OpenAI, Anthropic, Google Gemini) to intelligently auto-fill blank note fields. It supports text, audio (TTS), and image generation based on per-field instructions and optional user prompts.

## Features

- **Multi-provider support**: OpenAI, Anthropic (Claude), Google (Gemini), and OpenAI-compatible APIs.
- **Smart filling**: Automatically decides content type (text, audio, image) or follows your strict rules.
- **Batch processing**: Fill multiple cards at once from the browser with a side-by-side review/edit workflow.
- **Per-field context**: Define what each field should contain for every note type.
- **Text-to-Speech**: Integrated TTS (OpenAI, Gemini) for audio fields.
- **Image Generation**: Integrated image generation (DALL-E, Gemini) for image fields.
- **Inline Images**: Optionally include small illustrations within text fields.
- **Flexible UI**: Toolbar buttons, context menus, and configurable keyboard shortcuts.
- **Settings Portability**: Export/import configuration with optional API key encryption.

## Installation

1. Copy the `Anki-AI-Filler` folder to your Anki addons directory:
   - **Windows**: `%APPDATA%\Anki2\addons21\`
   - **macOS**: `~/Library/Application Support/Anki2/addons21/`
   - **Linux**: `~/.local/share/Anki2/addons21/`
2. Restart Anki.
3. Configure via **Tools → AI Filler → Settings...**

## Quick Start

1. **API Keys**: In **Settings → AI Providers**, enter your API key and click the refresh icon to fetch models.
2. **Active Providers**: Choose which provider to use for Text, TTS, and Image generation.
3. **Instructions**: In **Settings → Note Types**, select a note type and describe what each field should contain (e.g., "Example sentence in French").
4. **Fill**: Open the editor and click **"AI Fill All"** or press `Ctrl+Shift+G`.

## Usage

### Editor

- **AI Fill All**: Fills all blank fields using configured instructions.
- **AI Fill Current**: Fills only the active field, optionally asking for a quick prompt.
- **Quick Config**: Right-click any field to instantly edit its instructions.

### Browser (Batch Fill)

1. Select cards of the same note type.
2. **Right-click → AI: Batch fill...**
3. Configure target fields and run.
4. Review changes in the side-by-side diff view, edit if needed, and apply.

## How It Works

1. Gathers all field values and instructions for the current note.
2. Sends structured context to the selected AI provider.
3. Parses the AI response and applies content:
   - **Text**: Formatted as HTML.
   - **Audio**: Generated via TTS and saved to the media folder.
   - **Images**: Generated via Image API and saved to the media folder.
4. Irrelevant fields are left untouched.

## Troubleshooting

- **Connection Error**: Check your API key and internet connection. Ensure the provider's API URL is correct.
- **Fields Not Filling**: Ensure fields are empty (the add-on won't overwrite), instructions are configured, and "Include in auto-fill" is checked.
- **Audio/Image Issues**: Verify that TTS/Image providers are not set to "Disabled" and models are selected.

## Development

### Setup

1. Install [uv](https://github.com/astral-sh/uv) (recommended) or use `pip`.
2. Install dev dependencies:

   ```bash
   uv sync --group dev
   ```

3. Run tests:

   ```bash
   uv run pytest tests/ -v
   ```

4. Build the `.ankiaddon` package:

   ```bash
   python build.py
   ```

### Project Structure (src/)

- `api/` — Communication logic with external provider APIs (OpenAI, Anthropic, Google).
- `core/` — Primary application logic, configuration management, and card-filling orchestrator.
- `ui/` — Desktop user interface components built with Qt.

### Requirements

- Anki 2.1.50+ (Qt6 recommended).
- Active API key for OpenAI, Anthropic, or Google Gemini.


## License & Contributing

Distributed under the MIT License. Contributions and bug reports are welcome on GitHub!

