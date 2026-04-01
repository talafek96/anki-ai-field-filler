# AI Filler for Anki 🧠

An intelligent, multi-provider auto-fill assistant for Anki that uses Large Language Models (LLMs) to populate your flashcards. Whether you need native-level example sentences, high-quality Text-to-Speech (TTS), or AI-generated illustrations, AI Filler streamlines your card creation workflow.

[![GitHub License](https://img.shields.io/github/license/talafek96/anki-ai-field-filler)](https://github.com/talafek96/anki-ai-field-filler/blob/main/LICENSE)
[![AnkiWeb](https://img.shields.io/badge/AnkiWeb-Addon-blue)](https://ankiweb.net/shared/info/XXXXXXX)

---

## ✨ Key Features

- **Multi-Provider Support**: Seamlessly integrate with OpenAI (GPT-4o/o1), Anthropic (Claude 3.5/3), Google (Gemini 1.5 Pro/Flash), and Vercel.
- **Auto-decide Framework**: The AI intelligently determines the best content type (text, audio, image) for a field based on your instructions.
- **Batch Processing**: Select dozens or hundreds of cards in the Browser and fill them simultaneously with a side-by-side review/edit interface.
- **Native TTS & Images**: Generate audio and images directly within the addon, saved automatically to your Anki media folder.
- **Rich Content Support**: Interleave text, images, and audio flags within a single field for complex learning materials.
- **Scoped Instructions**: Define field instructions globally or override them for specific decks to tailor content to your learning context.
- **Developer-Friendly**: Built with a modular architecture, making it easy to add new providers or UI components.

---

## 🚀 Quick Start in 60 Seconds

1.  **Install**: Copy the `Anki-AI-Filler` folder to your Anki addons directory and restart.
2.  **Configure API**: Go to **Tools → AI Filler → Settings → General** and enter your API key.
3.  **Fetch Models**: Click the **Refresh** icon next to the provider to fetch the latest available models.
4.  **Set Instructions**: In the **Note Types** tab, select your chosen note type and describe what each field should contain (e.g., *"Provide a simple Japanese sentence using the word in the Front field"*).
5.  **Fill**: Open the editor and click the **Sparkles (\u2728)** icon on the toolbar or press `Ctrl+Shift+G`.

---

## 🛠 Usage & Workflow

### 1. The Editor Integration
The addon adds two primary buttons to your Anki editor toolbar:
- **Fill All Blank Fields (\u2728)**: Analyzes the entire note and fills all empty fields that have instructions.
- **Fill Current Field (\u26a1)**: Focuses only on the active field. If "Show fill dialog" is enabled, it allows you to provide a one-off quick prompt for that specific field.

### 2. Browser Batch Fill
For bulk card creation, the Browser integration is unmatched:
1. Select the cards you want to process.
2. Right-click and choose **AI: Batch fill blank fields...**
3. Select the target fields and run the generation.
4. **Review & Edit**: A side-by-side diff view appears, showing the original vs. proposed content. You can manually edit the AI's output or regenerate specific fields before applying.

### 3. Quick Instruction Config
Need to tweak instructions on the fly? Right-click any field in the editor and select **AI: Configure instructions...** to update its definition without opening the main settings.

---

## 🏗 Modular Architecture (`src/`)

The project is structured into three distinct layers for maximum maintainability:

### **`src/core/` — The Brain**
- `field_filler.py`: The main orchestrator that builds prompts, calls APIs, and updates cards.
- `provider_factory.py`: Centralized registry that maps provider types to their implementations.
- `config_manager.py`: Handles complex configuration hierarchies (Global vs. Deck-specific).

### **`src/api/` — The Connectivity**
- Contains specific implementations for each AI service: `openai.py`, `anthropic.py`, `google.py`, and `vercel.py`.
- Each provider follows a standard interface for text, TTS, and image generation.

### **`src/ui/` — The Interface**
- Polished Qt6 components including the multi-tabbed Settings dialog, the Batch Fill Review system, and the progress indicators.
- Uses a unified design system defined in `styles.py`.

---

## 📖 Content Type Reference

When configuring a field, you can set its **Content Type**:
- **Auto**: The AI analyzes the field name and instructions to decide the format.
- **Text**: Standard plain text or HTML content.
- **Audio**: The AI generates a text transcript which is then passed to a TTS provider.
- **Image**: The AI generates an image prompt which is then passed to an Image generator.
- **Rich**: Supports mixed content using inline flags like `{{IMAGE: prompt}}` and `{{AUDIO: text}}`.

---

## 📂 Project Resources

- **`assets/`**: High-quality SVG icons and UI assets.
- **`ANKIWEB.md`**: Source for the official AnkiWeb listing.
- **`.github/`**: Workflow configurations and funding metadata.

---

## 🧪 Development & Contribution

AI Filler is built with transparency in mind. We use `uv` for dependency management and `pytest` for logic validation.

```bash
# Setup development environment
uv sync --group dev

# Run test suite
uv run pytest tests/ -v

# Build .ankiaddon package
python build_ankiaddon.py
```

Contributions are welcome! Please see the [Issues](https://github.com/talafek96/anki-ai-field-filler/issues) page for planned features and bug reports.

---

## ⚖\ufe0f License

Distributed under the **MIT License**. See `LICENSE` for more information. Developed with \u2764\ufe0f for the Anki community.
