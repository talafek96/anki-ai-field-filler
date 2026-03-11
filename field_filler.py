"""Core field filling orchestrator.

Builds prompts from note context and field instructions, calls the AI provider,
parses the structured response, dispatches media generation, and updates the editor.
"""

from __future__ import annotations

import json
import re
import threading
from typing import Any, Callable, Dict, List, Optional

from aqt import mw
from aqt.editor import Editor

from .config_manager import ConfigManager, FieldInstruction
from .media_handler import MediaHandler
from .providers import create_image_provider, create_text_provider, create_tts_provider
from .providers.base import ProviderError

SYSTEM_PROMPT = """\
You are an Anki flashcard field assistant. Your job is to fill in blank \
fields for a flashcard note, given context from already-filled fields \
and user-provided instructions.

RESPONSE FORMAT:
Return ONLY a valid JSON object (no markdown fences, no extra text) with \
this structure:
{
  "fields": {
    "FieldName": {"content": "generated content", "type": "text"},
    "OtherField": {"content": "text to be spoken aloud", "type": "audio"},
    "ImageField": {"content": "image generation prompt", "type": "image"},
    "RichField": {"content": "text with definition", "type": "text", \
"image_prompt": "a helpful illustration of the concept"},
    "SkippedField": null
  }
}

RULES:
- Only include fields listed under "Fields to Fill"
- For "text" type: provide the actual text/HTML content for the field
- For "audio" type: provide the exact text that should be spoken aloud \
for TTS synthesis
- For "image" type: provide a descriptive prompt for image generation \
(the entire field will be an image)
- Any field of type "text" may OPTIONALLY include an "image_prompt" key. \
If you believe a small illustration would significantly help the learner \
understand or remember the content, include an "image_prompt" with a \
descriptive prompt for image generation. The image will be appended below \
the text in the same field. Only add an image when it genuinely adds value.
- Set a field to null if you cannot meaningfully fill it or it seems \
irrelevant given the context
- Use the filled fields and field instructions as context to generate \
appropriate content
- Match the language and style appropriate for the note type and content
- Be concise and accurate — this is for flashcards, not essays
- If a field's type hint is "auto", decide the best content type based \
on the field name and instruction
- Use line breaks in text content where appropriate for readability"""


class FieldFiller:
    """Orchestrates AI-powered field filling."""

    def __init__(self) -> None:
        self._config = ConfigManager()

    def fill_fields(
        self,
        editor: Editor,
        target_fields: List[str],
        user_prompt: str = "",
        on_success: Optional[Callable[[], None]] = None,
        on_error: Optional[Callable[[str], None]] = None,
    ) -> None:
        """Fill specified fields using AI. Runs in a background thread."""
        note = editor.note
        if not note:
            if on_error:
                on_error("No note is currently open.")
            return

        note_type = note.note_type()
        note_type_name = note_type["name"]
        field_names = list(note.keys())
        field_values = {name: note[name] for name in field_names}
        field_instructions = self._config.get_field_instructions(note_type_name)

        user_message = self._build_user_prompt(
            note_type_name,
            field_values,
            field_instructions,
            target_fields,
            user_prompt,
        )

        def background() -> None:
            try:
                provider_config = self._config.get_active_text_provider()
                provider = create_text_provider(provider_config)
                response_text = provider.generate(SYSTEM_PROMPT, user_message)
                parsed = self._parse_response(response_text)

                results: Dict[str, Optional[str]] = {}
                for field_name in target_fields:
                    field_data = parsed.get(field_name)
                    if field_data is None:
                        results[field_name] = None
                        continue

                    content = field_data.get("content", "")
                    ftype = field_data.get("type", "text")

                    if ftype == "audio":
                        tts_config = self._config.get_active_tts_provider()
                        if tts_config:
                            tts = create_tts_provider(tts_config)
                            audio_bytes = tts.synthesize(content)
                            results[field_name] = MediaHandler.save_audio(
                                audio_bytes, field_name
                            )
                        else:
                            results[field_name] = self._to_html(content)
                    elif ftype == "image":
                        img_config = self._config.get_active_image_provider()
                        if img_config:
                            img_prov = create_image_provider(img_config)
                            img_bytes = img_prov.generate_image(content)
                            results[field_name] = MediaHandler.save_image(
                                img_bytes, field_name
                            )
                        else:
                            results[field_name] = None
                    else:
                        html = self._to_html(content)
                        # Handle optional inline image for text fields
                        image_prompt = field_data.get("image_prompt", "")
                        if image_prompt:
                            img_config = self._config.get_active_image_provider()
                            if img_config:
                                img_prov = create_image_provider(img_config)
                                img_bytes = img_prov.generate_image(image_prompt)
                                img_tag = MediaHandler.save_image(
                                    img_bytes, field_name
                                )
                                html = f"{html}<br><br>{img_tag}"
                        results[field_name] = html

                def apply() -> None:
                    self._apply_results(editor, results)
                    if on_success:
                        on_success()

                mw.taskman.run_on_main(apply)

            except Exception as e:
                msg = str(e)

                def report_error() -> None:
                    if on_error:
                        on_error(msg)

                mw.taskman.run_on_main(report_error)

        thread = threading.Thread(target=background, daemon=True)
        thread.start()

    def fill_all_blank(
        self,
        editor: Editor,
        user_prompt: str = "",
        on_success: Optional[Callable[[], None]] = None,
        on_error: Optional[Callable[[str], None]] = None,
    ) -> None:
        """Fill all blank fields that are marked for auto-fill."""
        note = editor.note
        if not note:
            if on_error:
                on_error("No note is currently open.")
            return

        note_type_name = note.note_type()["name"]
        instructions = self._config.get_field_instructions(note_type_name)

        blank_fields = []
        for name in note.keys():
            value = note[name].strip()
            if not value:
                instr = instructions.get(name)
                if instr is None or instr.auto_fill:
                    blank_fields.append(name)

        if not blank_fields:
            if on_error:
                on_error("No blank fields to fill.")
            return

        self.fill_fields(editor, blank_fields, user_prompt, on_success, on_error)

    def _build_user_prompt(
        self,
        note_type_name: str,
        field_values: Dict[str, str],
        field_instructions: Dict[str, FieldInstruction],
        target_fields: List[str],
        user_prompt: str,
    ) -> str:
        """Build the user prompt sent to the AI."""
        parts: List[str] = [f"Note Type: {note_type_name}\n"]

        parts.append("== Current Field Values ==")
        for name, value in field_values.items():
            display = value.strip() if value.strip() else "(empty)"
            parts.append(f"- {name}: {display}")
        parts.append("")

        has_instructions = any(
            fi.instruction for fi in field_instructions.values()
        )
        if has_instructions:
            parts.append("== Field Instructions ==")
            for name, instr in field_instructions.items():
                if instr.instruction:
                    type_hint = (
                        f" [{instr.field_type}]"
                        if instr.field_type != "auto"
                        else ""
                    )
                    parts.append(f"- {name}{type_hint}: {instr.instruction}")
            parts.append("")

        parts.append("== Fields to Fill ==")
        for name in target_fields:
            instr = field_instructions.get(name)
            hint = ""
            if instr and instr.field_type != "auto":
                hint = f" (expected type: {instr.field_type})"
            parts.append(f"- {name}{hint}")
        parts.append("")

        if user_prompt.strip():
            parts.append("== Additional Instructions ==")
            parts.append(user_prompt.strip())

        return "\n".join(parts)

    def _parse_response(self, response: str) -> Dict[str, Any]:
        """Parse the AI's JSON response into field data."""
        text = response.strip()

        if text.startswith("```"):
            lines = text.split("\n")
            lines = lines[1:]
            if lines and lines[-1].strip().startswith("```"):
                lines = lines[:-1]
            text = "\n".join(lines).strip()

        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", text, re.DOTALL)
            if match:
                try:
                    data = json.loads(match.group())
                except json.JSONDecodeError:
                    raise ProviderError(
                        f"Could not parse AI response as JSON:\n{text[:500]}"
                    )
            else:
                raise ProviderError(
                    f"Could not find JSON in AI response:\n{text[:500]}"
                )

        return data.get("fields", data)

    @staticmethod
    def _to_html(text: str) -> str:
        """Convert plain text to Anki-compatible HTML.

        Converts newlines to <br> tags, but leaves content that already
        contains HTML tags untouched.
        """
        if not text:
            return text
        # If the content already has HTML block/br tags, assume it's HTML
        if "<br" in text or "<p>" in text or "<div>" in text:
            return text
        return text.replace("\n", "<br>")

    @staticmethod
    def _apply_results(
        editor: Editor, results: Dict[str, Optional[str]]
    ) -> None:
        """Apply generated content to the editor's note fields."""
        note = editor.note
        if not note:
            return

        changed = False
        for field_name, content in results.items():
            if content is not None and field_name in note:
                note[field_name] = content
                changed = True

        if changed:
            editor.loadNoteKeepingFocus()
