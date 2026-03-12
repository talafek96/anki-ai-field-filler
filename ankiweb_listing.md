<!-- AnkiWeb Addon Listing — AI Field Filler

Paste each section into the corresponding field on the AnkiWeb
upload form at https://ankiweb.net/shared/addons/

This file is version-controlled so the listing stays in sync
with the codebase. It is excluded from the .ankiaddon package. -->

# Title

AI Field Filler 🧠 Free AI Auto-Fill (Text, TTS, Images · Your Own Key)

# Tags

ai, gpt, openai, anthropic, google, gemini, tts, text-to-speech, image-generation, auto-fill, field-filler, language-learning

# Support Page

https://github.com/talafek96/anki-ai-field-filler/issues

# Description

**AI Field Filler** uses AI to intelligently auto-fill blank note fields — text, audio (TTS), and images — using context from your already-filled fields and per-field instructions you configure.

**100% free and open-source.** Bring your own API key from OpenAI, Anthropic, or Google. No subscription, no middleman, no usage fees beyond what your provider charges. If you already have an API key, you're ready to go.

---

# Features

- **Multi-provider support** — OpenAI (GPT-5, GPT-4o, DALL-E, TTS), Anthropic (Claude), Google (Gemini, Nano Banana, Gemini TTS), and any OpenAI-compatible API
- **Smart field filling** — The AI decides the best content type for each field (text, audio, or image) and skips irrelevant ones
- **Text-to-speech** — Generates audio files using OpenAI TTS or Google Gemini TTS
- **Image generation** — Generates images using OpenAI DALL-E or Google Nano Banana
- **Optional inline images** — For text fields, the AI can add a helpful illustration below the text when it aids learning
- **Per-field instructions** — Describe what each field should contain per note type, giving the AI rich context
- **Dynamic model selection** — Model dropdowns with a refresh button that fetches available models directly from the provider's API
- **Mix and match providers** — Use Anthropic for text, OpenAI for TTS, and Google for images — each capability is independent
- **Multiple activation methods** — Editor toolbar buttons, right-click context menu, or configurable keyboard shortcuts
- **Comfortable settings UI** — Tabbed settings dialog for providers, note type instructions, and general settings

# Supported Providers

<table>
  <tr><th>Provider</th><th>Text</th><th>TTS</th><th>Image</th></tr>
  <tr><td>OpenAI</td><td>✓</td><td>✓</td><td>✓</td></tr>
  <tr><td>Anthropic (Claude)</td><td>✓</td><td>—</td><td>—</td></tr>
  <tr><td>Google (Gemini)</td><td>✓</td><td>✓</td><td>✓</td></tr>
</table>

Works with any OpenAI-compatible API (Azure OpenAI, local LLMs, etc.) by changing the API URL.

# Quick Start

1. Open **Tools → AI Field Filler → Settings...**
2. Enter your API key for your preferred provider
3. Click **Test Connection** to verify
4. Go to the **Note Types** tab and describe what each field should contain
5. Open a note in the editor and click **AI Fill All** or press `Ctrl+Shift+G`

# How It Works

1. When you trigger a fill action, the addon gathers all field values, per-field instructions, and your optional prompt
2. This context is sent to your AI provider as a structured prompt
3. The AI returns content for each field, deciding the best type (text, audio, or image)
4. **Text fields:** content is inserted as HTML; the AI may optionally include a generated illustration
5. **Audio fields:** text is sent to the TTS provider and saved as a playable sound file
6. **Image fields:** a generation prompt is sent to the image provider and saved as an image
7. Fields the AI deems irrelevant are left empty

# Usage

- **Fill All Blank Fields:** toolbar button, right-click menu, or `Ctrl+Shift+G`
- **Fill Current Field:** toolbar button, right-click menu, or `Ctrl+Shift+F`
- **Quick Configure:** right-click any field → "AI: Configure instructions..." to set instructions inline

# Requirements

- Anki 2.1.50 or later (Qt6 recommended)
- An API key for at least one supported provider (OpenAI, Anthropic, or Google)
- Internet connection

# Support

Bug reports, feature requests, and contributions are welcome on [GitHub](https://github.com/talafek96/anki-ai-field-filler).
