"""Tests for prompt building in FieldFiller."""

from __future__ import annotations

from ai_field_filler.config_manager import FieldInstruction


class TestBuildUserPrompt:
    """Tests for FieldFiller._build_user_prompt."""

    def test_basic_prompt_structure(self, filler) -> None:
        prompt = filler._build_user_prompt(
            note_type_name="Basic",
            field_values={"Front": "hello", "Back": ""},
            field_instructions={},
            target_fields=["Back"],
            user_prompt="",
        )
        assert "Note Type: Basic" in prompt
        assert "Front: hello" in prompt
        assert "Back: (empty)" in prompt
        assert "== Fields to Fill ==" in prompt
        assert "- Back" in prompt

    def test_field_instructions_included(self, filler) -> None:
        instructions = {
            "Meaning": FieldInstruction(
                instruction="English definition", field_type="text"
            ),
        }
        prompt = filler._build_user_prompt(
            note_type_name="Japanese",
            field_values={"Word": "\u98df\u3079\u308b", "Meaning": ""},
            field_instructions=instructions,
            target_fields=["Meaning"],
            user_prompt="",
        )
        assert "== Field Instructions ==" in prompt
        assert "Meaning [text]: English definition" in prompt

    def test_auto_type_no_bracket(self, filler) -> None:
        instructions = {
            "Meaning": FieldInstruction(
                instruction="English def", field_type="auto"
            ),
        }
        prompt = filler._build_user_prompt(
            note_type_name="Test",
            field_values={"Meaning": ""},
            field_instructions=instructions,
            target_fields=["Meaning"],
            user_prompt="",
        )
        assert "Meaning: English def" in prompt
        assert "[auto]" not in prompt

    def test_user_prompt_appended(self, filler) -> None:
        prompt = filler._build_user_prompt(
            note_type_name="Basic",
            field_values={"Front": "x", "Back": ""},
            field_instructions={},
            target_fields=["Back"],
            user_prompt="Use simple language",
        )
        assert "== Additional Instructions ==" in prompt
        assert "Use simple language" in prompt

    def test_no_instructions_section_when_empty(self, filler) -> None:
        prompt = filler._build_user_prompt(
            note_type_name="Basic",
            field_values={"Front": "x"},
            field_instructions={},
            target_fields=["Front"],
            user_prompt="",
        )
        assert "== Field Instructions ==" not in prompt

    def test_no_additional_section_when_blank(self, filler) -> None:
        prompt = filler._build_user_prompt(
            note_type_name="Basic",
            field_values={"Front": "x"},
            field_instructions={},
            target_fields=["Front"],
            user_prompt="   ",
        )
        assert "== Additional Instructions ==" not in prompt

    def test_expected_type_hint_in_fields_to_fill(self, filler) -> None:
        instructions = {
            "Audio": FieldInstruction(
                instruction="pronunciation", field_type="audio"
            ),
        }
        prompt = filler._build_user_prompt(
            note_type_name="Test",
            field_values={"Audio": ""},
            field_instructions=instructions,
            target_fields=["Audio"],
            user_prompt="",
        )
        assert "Audio (expected type: audio)" in prompt

    def test_multiple_target_fields(self, filler) -> None:
        prompt = filler._build_user_prompt(
            note_type_name="Multi",
            field_values={"A": "", "B": "", "C": "filled"},
            field_instructions={},
            target_fields=["A", "B"],
            user_prompt="",
        )
        assert "- A" in prompt
        assert "- B" in prompt
        assert "C: filled" in prompt
