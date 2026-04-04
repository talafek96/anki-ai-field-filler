"""Core field filling orchestrator.

Builds prompts from note context and field instructions, calls the AI provider,
parses the structured response, dispatches media generation, and updates the editor.
"""

from __future__ import annotations

import json
import re
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, TypeVar

from aqt import mw
from aqt.editor import Editor

from .config import Config, FieldInstruction
from .factory import create_image_provider, create_text_provider, create_tts_provider
from .interfaces import ProviderError
from .media import Media

# ---------------------------------------------------------------------------
# Retry helper for all generation calls
# ---------------------------------------------------------------------------

_T = TypeVar("_T")

# Error codes / substrings that indicate unrecoverable failures.
_NON_RETRYABLE_TOKENS = {
    "error 401",
    "error 403",
    "unauthorized",
    "forbidden",
    "invalid_api_key",
}

_GENERATION_MAX_RETRIES = 3
_GENERATION_RETRY_BASE = 1.0  # seconds


def _is_retryable(exc: Exception) -> bool:
    """Return False for authentication / permission errors that will never succeed on retry."""
    msg = str(exc).lower()
    return not any(tok in msg for tok in _NON_RETRYABLE_TOKENS)


def with_retry(fn: Callable[..., _T], *args: Any, **kwargs: Any) -> _T:
    """Call *fn* up to ``_GENERATION_MAX_RETRIES`` times with exponential backoff.

    Raises immediately on non-retryable errors (auth / permission).
    On the final attempt the error propagates as-is.
    """
    last_error: Exception | None = None
    for attempt in range(_GENERATION_MAX_RETRIES):
        try:
            return fn(*args, **kwargs)
        except Exception as e:
            last_error = e
            if not _is_retryable(e) or attempt == _GENERATION_MAX_RETRIES - 1:
                if attempt > 0:
                    raise type(e)(f"{e} (failed after {attempt + 1} attempts)") from e
                raise
            time.sleep(_GENERATION_RETRY_BASE * (2**attempt))
    raise last_error  # type: ignore[misc]


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
    "RichField": {"content": "Definition of the word\\n\
{{IMAGE: a helpful illustration of the concept}}\\n\
Pronunciation:\\n{{AUDIO: the word spoken aloud}}", "type": "rich"},
    "SkippedField": null
  }
}

INLINE MEDIA FLAGS:
You can embed images and audio anywhere inside a field's content using \
these flags:
- {{IMAGE: descriptive prompt for image generation}} — will be replaced \
with a generated image
- {{AUDIO: exact text to be spoken aloud}} — will be replaced with a \
TTS audio clip
Place flags exactly where you want the media to appear in the field. \
You may use multiple flags in a single field. These flags work in ANY \
field type (text, rich, or auto).

RULES:
- Only include fields listed under "Fields to Fill"
- For "text" type: provide the actual text/HTML content for the field. \
You may include {{IMAGE: ...}} or {{AUDIO: ...}} flags inline if media \
would help the learner.
- For "audio" type: provide the exact text that should be spoken aloud \
for TTS synthesis (the entire field becomes an audio file)
- For "image" type: provide a descriptive prompt for image generation \
(the entire field will be an image)
- For "rich" type: provide content that freely mixes text with inline \
{{IMAGE: ...}} and {{AUDIO: ...}} flags. Use this when a field benefits \
from interleaved text, images, and audio.
- Set a field to null if you cannot meaningfully fill it or it seems \
irrelevant given the context
- Use the filled fields and field instructions as context to generate \
appropriate content
- Match the language and style appropriate for the note type and content
- Be concise and accurate — this is for flashcards, not essays
- If a field's type hint is "auto", decide the best content type based \
on the field name and instruction
- Use line breaks in text content where appropriate for readability"""


class Filler:
    """Orchestrates AI-powered field filling."""

    def __init__(self) -> None:
        self._config = Config()

    @staticmethod
    def _build_tts_context(note_type_name: str, field_values: Dict[str, str]) -> str:
        """Build a compact context string for TTS pronunciation guidance."""
        lines = [f"Note type: {note_type_name}"]
        for name, value in field_values.items():
            text = value.strip()
            if text:
                # Truncate long values to keep the context concise
                preview = text[:120] + "…" if len(text) > 120 else text
                lines.append(f"  {name}: {preview}")
        return "\n".join(lines)

    def fill_fields(
        self,
        editor: Editor,
        target_fields: List[str],
        user_prompt: str = "",
        on_success: Optional[Callable[[], None]] = None,
        on_error: Optional[Callable[[str], None]] = None,
        deck_name: Optional[str] = None,
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
        field_instructions = self._config.get_field_instructions(
            note_type_name, deck_name=deck_name
        )

        user_message = self._build_user_prompt(
            note_type_name,
            field_values,
            field_instructions,
            target_fields,
            user_prompt,
        )
        tts_context = self._build_tts_context(note_type_name, field_values)

        def background() -> None:
            try:
                parsed = self._generate_and_parse(SYSTEM_PROMPT, user_message)

                results: Dict[str, Optional[str]] = {}
                field_errors: List[str] = []
                for field_name in target_fields:
                    field_data = parsed.get(field_name)
                    if field_data is None:
                        results[field_name] = None
                        continue

                    content = field_data.get("content", "")
                    ftype = field_data.get("type", "text")

                    try:
                        if ftype == "audio":
                            tts_config = self._config.get_active_tts_provider()
                            if tts_config:
                                tts = create_tts_provider(tts_config)
                                audio_bytes = with_retry(
                                    tts.synthesize, content, context=tts_context
                                )
                                results[field_name] = Media.save_audio(
                                    audio_bytes, field_name
                                )
                            else:
                                results[field_name] = self._to_html(content)
                        elif ftype == "image":
                            img_config = self._config.get_active_image_provider()
                            if img_config:
                                img_prov = create_image_provider(img_config)
                                img_bytes = with_retry(img_prov.generate_image, content)
                                results[field_name] = Media.save_image(
                                    img_bytes, field_name
                                )
                            else:
                                results[field_name] = None
                            # If rich/flags fail, we still have the text 'content'
                            html, errs = self._render_rich_content(
                                content,
                                field_name,
                                field_data,
                                tts_context=tts_context,
                            )
                            # We don't add to field_errors if we have html
                            if not html and errs:
                                field_errors.extend(errs)
                            results[field_name] = html or self._to_html(content)
                        else:
                            html = self._to_html(content)
                            # Handle optional inline image for text fields
                            image_prompt = field_data.get("image_prompt", "")
                            if image_prompt:
                                try:
                                    img_config = (
                                        self._config.get_active_image_provider()
                                    )
                                    if img_config:
                                        img_prov = create_image_provider(img_config)
                                        img_bytes = with_retry(
                                            img_prov.generate_image, image_prompt
                                        )
                                        img_tag = Media.save_image(
                                            img_bytes, field_name
                                        )
                                        html = f"{html}<br><br>{img_tag}"
                                except Exception as img_err:
                                    field_errors.append(
                                        f"{field_name} (inline image,"
                                        f" prompt: {image_prompt!r}): {img_err}"
                                    )
                            results[field_name] = html
                    except Exception as e:
                        field_errors.append(f"{field_name} (prompt: {content!r}): {e}")
                        results[field_name] = None

                # Targeted retry: if some fields are missing, make a cheaper
                # follow-up call for just those fields instead of re-running all.
                missing = [f for f in target_fields if results.get(f) is None]
                if missing:
                    try:
                        retry_msg = self._build_user_prompt(
                            note_type_name,
                            field_values,
                            field_instructions,
                            missing,
                            user_prompt,
                        )
                        retry_parsed = self._generate_and_parse(
                            SYSTEM_PROMPT, retry_msg
                        )
                        for fname in missing:
                            fdata = retry_parsed.get(fname)
                            if fdata is None:
                                continue
                            fc = fdata.get("content", "")
                            ft = fdata.get("type", "text")
                            try:
                                if ft == "audio":
                                    tc = self._config.get_active_tts_provider()
                                    if tc:
                                        t = create_tts_provider(tc)
                                        ab = with_retry(
                                            t.synthesize, fc, context=tts_context
                                        )
                                        results[fname] = Media.save_audio(ab, fname)
                                elif ft == "image":
                                    ic = self._config.get_active_image_provider()
                                    if ic:
                                        ip = create_image_provider(ic)
                                        ib = with_retry(ip.generate_image, fc)
                                        results[fname] = Media.save_image(ib, fname)
                                elif ft == "rich" or self._has_flags(fc):
                                    h, errs = self._render_rich_content(
                                        fc, fname, fdata, tts_context=tts_context
                                    )
                                    field_errors.extend(errs)
                                    results[fname] = h
                                else:
                                    results[fname] = self._to_html(fc)
                            except Exception:
                                pass  # retry for this field also failed
                    except Exception:
                        pass  # follow-up call failed — keep the partial results

                def apply() -> None:
                    self._apply_results(editor, results)

                    filled = [f for f, v in results.items() if v is not None]
                    failed = [f for f in target_fields if results.get(f) is None]

                    if failed and on_error:
                        parts: List[str] = []
                        if filled:
                            parts.append(
                                "Fields filled successfully: " + ", ".join(filled)
                            )
                        parts.append("Failed fields:")
                        # Find original errors for these failed fields
                        for f in failed:
                            # Try to find a matching error message
                            found = False
                            for e in field_errors:
                                if e.startswith(f):
                                    parts.append(f"  \u2022 {e}")
                                    found = True
                            if not found:
                                parts.append(f"  \u2022 {f}: Unknown conversion error")
                        on_error("\n".join(parts))
                    elif on_success:
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

        has_instructions = any(fi.instruction for fi in field_instructions.values())
        if has_instructions:
            parts.append("== Field Instructions ==")
            for name, instr in field_instructions.items():
                if instr.instruction:
                    type_hint = (
                        f" [{instr.field_type}]" if instr.field_type != "auto" else ""
                    )
                    parts.append(f"- {name}{type_hint}: {instr.instruction}")
            parts.append("")

        parts.append("== Fields to Fill ==")
        for name in target_fields:
            fi = field_instructions.get(name)
            hint = ""
            if fi and fi.field_type != "auto":
                hint = f" (expected type: {fi.field_type})"
            parts.append(f"- {name}{hint}")
        parts.append("")

        if user_prompt.strip():
            parts.append("== Additional Instructions ==")
            parts.append(user_prompt.strip())

        return "\n".join(parts)

    def _generate_and_parse(
        self, system_prompt: str, user_message: str
    ) -> Dict[str, Any]:
        """Call the AI provider and parse the response.

        Retries the full generate+parse cycle up to 3 times with exponential
        backoff.  Non-retryable errors (auth / permissions) propagate immediately.
        """
        provider_config = self._config.get_active_text_provider()
        provider = create_text_provider(provider_config)

        def _attempt() -> Dict[str, Any]:
            response_text = provider.generate(system_prompt, user_message)
            return self._parse_response(response_text)

        return with_retry(_attempt)

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

    _FLAG_RE = re.compile(r"\{\{(IMAGE|AUDIO):\s*(.*?)\}\}", re.DOTALL)

    def _render_flags(
        self,
        content: str,
        field_name: str,
        tts_context: str = "",
    ) -> tuple[str, List[str]]:
        """Replace ``{{IMAGE: …}}`` / ``{{AUDIO: …}}`` flags with generated media.

        Returns ``(rendered_html, errors)`` where *errors* lists any flags
        whose media generation failed (the flag is removed from the output).
        """
        errors: List[str] = []
        flag_idx = 0

        def _replace_flag(match: re.Match) -> str:  # type: ignore[type-arg]
            nonlocal flag_idx
            flag_idx += 1
            kind = match.group(1)  # IMAGE or AUDIO
            payload = match.group(2).strip()
            if not payload:
                return ""

            part_name = f"{field_name}_p{flag_idx}"
            try:
                if kind == "IMAGE":
                    img_config = self._config.get_active_image_provider()
                    if img_config:
                        img_prov = create_image_provider(img_config)
                        img_bytes = with_retry(img_prov.generate_image, payload)
                        return Media.save_image(img_bytes, part_name)
                    return ""
                else:  # AUDIO
                    tts_config = self._config.get_active_tts_provider()
                    if tts_config:
                        tts = create_tts_provider(tts_config)
                        audio_bytes = with_retry(
                            tts.synthesize, payload, context=tts_context
                        )
                        return Media.save_audio(audio_bytes, part_name)
                    return ""
            except Exception as e:
                errors.append(
                    f"{field_name} ({kind.lower()} flag, prompt: {payload!r}): {e}"
                )
                return ""

        rendered = self._FLAG_RE.sub(_replace_flag, content)
        rendered = self._to_html(rendered)
        return rendered, errors

    def _has_flags(self, content: str) -> bool:
        """Return True if *content* contains any media flags."""
        return self._FLAG_RE.search(content) is not None

    def _render_rich_content(
        self,
        content: str,
        field_name: str,
        field_data: Dict[str, Any],
        tts_context: str = "",
    ) -> tuple[str, List[str]]:
        """Render content with inline media flags and optional legacy *image_prompt*.

        Returns ``(html, errors)`` where *errors* lists any media operations
        that failed.
        """
        html, errors = self._render_flags(content, field_name, tts_context=tts_context)
        # Also honour legacy image_prompt if present
        image_prompt = field_data.get("image_prompt", "")
        if image_prompt:
            try:
                img_config = self._config.get_active_image_provider()
                if img_config:
                    img_prov = create_image_provider(img_config)
                    img_bytes = with_retry(img_prov.generate_image, image_prompt)
                    img_tag = Media.save_image(img_bytes, field_name)
                    html = f"{html}<br><br>{img_tag}"
            except Exception as img_err:
                errors.append(
                    f"{field_name} (inline image, prompt: {image_prompt!r}): {img_err}"
                )
        return html, errors

    @staticmethod
    def _apply_results(editor: Editor, results: Dict[str, Optional[str]]) -> None:
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


# ---------------------------------------------------------------------------
# Batch fill
# ---------------------------------------------------------------------------


@dataclass
class BatchNoteResult:
    """Result of processing a single note in a batch."""

    note_id: int
    success: bool
    fields_filled: int = 0
    error: str = ""


@dataclass
class BatchProposedChange:
    """A single proposed field change for review before applying."""

    note_id: int
    note_preview: str  # first non-empty field for identification
    blank_fields: List[str]  # fields that would be targeted
    changes: Dict[str, str] = field(default_factory=dict)  # field → new value
    original_values: Dict[str, str] = field(default_factory=dict)  # field → old value
    error: str = ""
    field_errors: Dict[str, str] = field(default_factory=dict)  # per-field errors

    @property
    def success(self) -> bool:
        return not self.error


@dataclass
class BatchProgress:
    """Snapshot of batch progress, passed to the UI callback."""

    completed: int
    total: int
    current_note_preview: str = ""
    elapsed_seconds: float = 0.0
    eta_seconds: float = 0.0


@dataclass
class BatchResult:
    """Final result of a batch fill operation."""

    total: int = 0
    succeeded: int = 0
    failed: int = 0
    skipped: int = 0
    elapsed_seconds: float = 0.0
    failures: List[BatchNoteResult] = field(default_factory=list)
    proposals: List[BatchProposedChange] = field(default_factory=list)
    dry_run: bool = False


@dataclass
class BatchNoteItem:
    """A note to process in a batch, paired with its deck context."""

    note_id: int
    deck_name: Optional[str] = None


class BatchFiller:
    """Processes multiple notes sequentially with progress reporting."""

    def __init__(self) -> None:
        self._config = Config()
        self._filler = Filler()
        self._cancelled = False

    def cancel(self) -> None:
        """Request cancellation (takes effect after the current note)."""
        self._cancelled = True

    @property
    def is_cancelled(self) -> bool:
        return self._cancelled

    def run(
        self,
        items: List[BatchNoteItem],
        target_fields: List[str],
        user_prompt: str = "",
        dry_run: bool = False,
        on_progress: Optional[Callable[[BatchProgress], None]] = None,
    ) -> BatchResult:
        """Process notes sequentially. Call from a background thread.

        When *dry_run* is True, no AI calls are made — the result contains
        :attr:`BatchResult.proposals` with the blank fields that *would* be
        targeted per note.

        Otherwise, proposals are populated with the generated content so the
        caller can present a review dialog before committing.

        *on_progress* is called (on the calling thread) after each note.
        """
        self._cancelled = False
        result = BatchResult(total=len(items), dry_run=dry_run)
        start = time.monotonic()

        for idx, item in enumerate(items):
            if self._cancelled:
                result.skipped = result.total - idx
                break

            note = mw.col.get_note(item.note_id)
            note_type_name = note.note_type()["name"]
            preview = self._note_preview(note)

            # Show which note we're about to process
            self._report_progress(on_progress, idx, result.total, note, start)

            # Determine which target fields are actually blank for this note
            blank_targets = [f for f in target_fields if not note[f].strip()]
            if not blank_targets:
                result.skipped += 1
                self._report_progress(on_progress, idx + 1, result.total, note, start)
                continue

            field_instructions = self._config.get_field_instructions(
                note_type_name, deck_name=item.deck_name
            )

            orig_values = {f: note[f] for f in blank_targets}

            if dry_run:
                result.proposals.append(
                    BatchProposedChange(
                        note_id=item.note_id,
                        note_preview=preview,
                        blank_fields=blank_targets,
                        original_values=orig_values,
                    )
                )
                result.succeeded += 1
                self._report_progress(on_progress, idx + 1, result.total, note, start)
                continue

            # Generate content (but don't write to note yet)
            try:
                field_values = {name: note[name] for name in note.keys()}
                tts_ctx = Filler._build_tts_context(note_type_name, field_values)
                user_message = self._filler._build_user_prompt(
                    note_type_name,
                    field_values,
                    field_instructions,
                    blank_targets,
                    user_prompt,
                )
                parsed = self._filler._generate_and_parse(SYSTEM_PROMPT, user_message)
                changes, field_errors = self._render_fields(
                    parsed, blank_targets, tts_context=tts_ctx
                )

                # Targeted retry: if some fields are missing from the result,
                # make a cheaper follow-up call for just those fields.
                missing = [f for f in blank_targets if f not in changes]
                if missing:
                    try:
                        retry_msg = self._filler._build_user_prompt(
                            note_type_name,
                            field_values,
                            field_instructions,
                            missing,
                            user_prompt,
                        )
                        retry_parsed = self._filler._generate_and_parse(
                            SYSTEM_PROMPT, retry_msg
                        )
                        retry_changes, retry_errors = self._render_fields(
                            retry_parsed, missing, tts_context=tts_ctx
                        )
                        changes.update(retry_changes)
                        field_errors.update(retry_errors)
                    except Exception:
                        pass  # follow-up failed — keep the partial results we have

                result.proposals.append(
                    BatchProposedChange(
                        note_id=item.note_id,
                        note_preview=preview,
                        blank_fields=blank_targets,
                        changes=changes,
                        original_values=orig_values,
                        field_errors=field_errors,
                    )
                )
                result.succeeded += 1
            except Exception as e:
                result.proposals.append(
                    BatchProposedChange(
                        note_id=item.note_id,
                        note_preview=preview,
                        blank_fields=blank_targets,
                        original_values=orig_values,
                        error=str(e),
                    )
                )
                nr = BatchNoteResult(note_id=item.note_id, success=False, error=str(e))
                result.failed += 1
                result.failures.append(nr)

            self._report_progress(on_progress, idx + 1, result.total, note, start)

        result.elapsed_seconds = time.monotonic() - start
        return result

    def apply_proposals(
        self,
        proposals: List[BatchProposedChange],
    ) -> int:
        """Write approved proposals to their notes. Returns count applied.

        Call from the main thread after the user has reviewed and approved.
        """
        applied = 0
        for prop in proposals:
            if not prop.success or not prop.changes:
                continue
            note = mw.col.get_note(prop.note_id)
            changed = False
            for field_name, new_value in prop.changes.items():
                if field_name in note:
                    note[field_name] = new_value
                    changed = True
            if changed:
                note.flush()
                applied += 1
        return applied

    def regenerate_field(
        self,
        note_id: int,
        field_name: str,
        user_prompt: str = "",
        deck_name: Optional[str] = None,
    ) -> tuple:
        """Regenerate a single field for a note. Call from a background thread.

        Returns ``(new_value, error)`` where *error* is an empty string on
        success.
        """
        try:
            note = mw.col.get_note(note_id)
            note_type_name = note.note_type()["name"]
            field_values = {name: note[name] for name in note.keys()}
            field_instructions = self._config.get_field_instructions(
                note_type_name, deck_name=deck_name
            )
            tts_ctx = Filler._build_tts_context(note_type_name, field_values)
            user_message = self._filler._build_user_prompt(
                note_type_name,
                field_values,
                field_instructions,
                [field_name],
                user_prompt,
            )
            parsed = self._filler._generate_and_parse(SYSTEM_PROMPT, user_message)
            changes, field_errors = self._render_fields(
                parsed, [field_name], tts_context=tts_ctx
            )
            new_value = changes.get(field_name, "")
            error = field_errors.get(field_name, "")
            return (new_value, error)
        except Exception as e:
            return ("", str(e))

    def _render_fields(
        self,
        parsed: Dict[str, Any],
        target_fields: List[str],
        tts_context: str = "",
    ) -> tuple[Dict[str, str], Dict[str, str]]:
        """Render parsed AI output into final field values (HTML/media).

        Returns a tuple of ``(changes, field_errors)`` where *changes* maps
        field names to rendered values and *field_errors* maps field names
        to error messages for fields whose media generation failed.
        """
        changes: Dict[str, str] = {}
        field_errors: Dict[str, str] = {}
        for field_name in target_fields:
            field_data = parsed.get(field_name)
            if field_data is None:
                continue

            content = field_data.get("content", "")
            ftype = field_data.get("type", "text")

            try:
                if ftype == "audio":
                    tts_config = self._config.get_active_tts_provider()
                    if tts_config:
                        tts = create_tts_provider(tts_config)
                        audio_bytes = with_retry(
                            tts.synthesize, content, context=tts_context
                        )
                        changes[field_name] = Media.save_audio(audio_bytes, field_name)
                    else:
                        html = Filler._to_html(content)
                        if html:
                            changes[field_name] = html
                elif ftype == "image":
                    img_config = self._config.get_active_image_provider()
                    if img_config:
                        img_prov = create_image_provider(img_config)
                        img_bytes = with_retry(img_prov.generate_image, content)
                        changes[field_name] = Media.save_image(img_bytes, field_name)
                elif ftype == "rich" or self._filler._has_flags(content):
                    html, errs = self._filler._render_rich_content(
                        content, field_name, field_data, tts_context=tts_context
                    )
                    if errs:
                        field_errors[field_name] = "; ".join(errs)
                    if html:
                        changes[field_name] = html
                else:
                    html = Filler._to_html(content)
                    image_prompt = field_data.get("image_prompt", "")
                    if image_prompt:
                        try:
                            img_config = self._config.get_active_image_provider()
                            if img_config:
                                img_prov = create_image_provider(img_config)
                                img_bytes = with_retry(
                                    img_prov.generate_image, image_prompt
                                )
                                img_tag = Media.save_image(img_bytes, field_name)
                                html = f"{html}<br><br>{img_tag}"
                        except Exception as img_err:
                            # Keep the text, just note the inline image failure
                            field_errors[field_name] = (
                                f"Text kept, but inline image failed: {img_err}"
                                f" (prompt: {image_prompt!r})"
                            )
                    if html:
                        changes[field_name] = html
            except Exception as e:
                field_errors[field_name] = f"{e} (prompt: {content!r})"

        return changes, field_errors

    @staticmethod
    def _note_preview(note: Any) -> str:
        """Return a short preview string from the first non-empty field."""
        for name in note.keys():
            val = note[name].strip()
            if val:
                return val[:60] + ("..." if len(val) > 60 else "")
        return "(empty note)"

    @staticmethod
    def _report_progress(
        callback: Optional[Callable[[BatchProgress], None]],
        completed: int,
        total: int,
        note: Any,
        start_time: float,
    ) -> None:
        if not callback:
            return
        elapsed = time.monotonic() - start_time
        rate = completed / elapsed if elapsed > 0 else 0
        remaining = total - completed
        eta = remaining / rate if rate > 0 else 0.0
        preview = BatchFiller._note_preview(note)
        callback(
            BatchProgress(
                completed=completed,
                total=total,
                current_note_preview=preview,
                elapsed_seconds=elapsed,
                eta_seconds=eta,
            )
        )
