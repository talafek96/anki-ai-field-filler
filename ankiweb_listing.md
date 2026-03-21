<!-- AnkiWeb Addon Listing — AI Field Filler

Paste each section into the corresponding field on the AnkiWeb
upload form at https://ankiweb.net/shared/addons/

This file is version-controlled so the listing stays in sync
with the codebase. It is excluded from the .ankiaddon package. -->

# Title

AI Field Filler 🧠 Smart Auto-Fill for Notes (Text, TTS, Images)

# Tags

ai, gpt, openai, anthropic, google, gemini, tts, text-to-speech, image-generation, auto-fill, field-filler, language-learning, batch-fill

# Support Page

https://github.com/talafek96/anki-ai-field-filler/issues

# Description

**AI Field Filler** uses AI to intelligently fill blank note fields - text, audio (TTS), and images - based on your existing note content and the per-field instructions you configure.

**Free and open-source.** Use your own API key from OpenAI, Anthropic, or Google. No subscription, no middleman.

---

# See It in Action

**Fill all blank fields in one go**

<img src="https://raw.githubusercontent.com/talafek96/anki-ai-field-filler/main/assets/fill_all_demo.gif" width="900"><br><br>

**Fill the current field from the right-click menu**

<img src="https://raw.githubusercontent.com/talafek96/anki-ai-field-filler/main/assets/fill_current_right_click_demo.gif" width="900"><br><br>

**Generate image and sound for the current field**

<img src="https://raw.githubusercontent.com/talafek96/anki-ai-field-filler/main/assets/fill_current_img_and_sound_demo.gif" width="900"><br><br>

---

# Why Use It

- Fill missing fields faster without manually copy-pasting prompts
- Generate text, TTS, and images in one workflow
- Configure exactly what each field should contain per note type
- Use different AI providers for different tasks
- Review batch-generated changes before applying them

---

# Batch Fill Workflow

Select multiple cards in the browser, generate fills for all blank fields, review side-by-side diffs, edit results, and apply only the changes you approve.

<img src="https://raw.githubusercontent.com/talafek96/anki-ai-field-filler/main/assets/batch_fill_demo.gif" width="900"><br><br>

---

# Features

- **Smart field filling** - The AI decides the best content type for each field and skips irrelevant ones
- **Text generation** - Fill blank text fields using context from your existing fields and instructions
- **Text-to-speech** - Generate audio using OpenAI TTS or Google Gemini TTS
- **Image generation** - Generate images using OpenAI DALL-E or Google Nano Banana
- **Optional inline images** - Add a helpful illustration below generated text when it supports learning
- **Per-field instructions** - Define what each field should contain for each note type
- **Batch fill from browser** - Fill many notes at once with progress, diff review, editing, and selective apply
- **Dynamic model selection** - Refresh model lists directly from each provider
- **Mix and match providers** - Use different providers for text, TTS, and images independently
- **Multiple activation methods** - Toolbar buttons, right-click menu, batch fill, and keyboard shortcuts
- **Comfortable settings UI** - Tabbed settings for providers, note type instructions, and general options

---

# Supported Providers

- **OpenAI** - Text, TTS, Image
- **Anthropic (Claude)** - Text
- **Google (Gemini)** - Text, TTS, Image

Works with any OpenAI-compatible API (Azure OpenAI, local LLMs, etc.) by changing the API URL.

---

# Flexible Configuration

Choose different providers for text, TTS, and images. Configure per-field instructions for each note type, and refresh available models directly from the provider APIs.

<img src="https://raw.githubusercontent.com/talafek96/anki-ai-field-filler/main/assets/settings_demo.gif" width="900"><br><br>

---

# Quick Start

1. Open **Tools → AI Field Filler → Settings...**
2. Enter your API key for your preferred provider
3. Click **Test Connection**
4. Go to the **Note Types** tab and describe what each field should contain
5. Open a note in the editor and click **AI Fill All** or press `Ctrl+Shift+G`

---

# Usage

- **Fill All Blank Fields** - toolbar button, right-click menu, or `Ctrl+Shift+G`
- **Fill Current Field** - toolbar button, right-click menu, or `Ctrl+Shift+F`
- **Batch Fill** - select cards in the browser → right-click → "AI: Batch fill blank fields" → configure → review diffs → apply
- **Quick Configure** - right-click any field → "AI: Configure instructions..." to set instructions inline

---

# How It Works

1. When you trigger a fill action, the addon gathers all field values, per-field instructions, and your optional prompt
2. This context is sent to your AI provider as a structured prompt
3. The AI returns content for each field, deciding the best type (text, audio, or image)
4. **Text fields** - content is inserted as HTML; the AI may optionally include a generated illustration
5. **Audio fields** - text is sent to the TTS provider and saved as a playable sound file
6. **Image fields** - a generation prompt is sent to the image provider and saved as an image
7. Fields the AI deems irrelevant are left empty

---

# Requirements

- Anki 2.1.50 or later (Qt6 recommended)
- An API key for at least one supported provider (OpenAI, Anthropic, or Google)
- Internet connection

---

# Support

Bug reports, feature requests, and contributions are welcome on [GitHub](https://github.com/talafek96/anki-ai-field-filler).
