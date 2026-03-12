"""Tests for ConfigManager dataclasses and config logic."""

from __future__ import annotations

from ai_field_filler.config_manager import (
    FieldInstruction,
    GeneralSettings,
    ProviderConfig,
)


class TestFieldInstruction:
    def test_defaults(self) -> None:
        fi = FieldInstruction()
        assert fi.instruction == ""
        assert fi.field_type == "auto"
        assert fi.auto_fill is True

    def test_custom_values(self) -> None:
        fi = FieldInstruction(
            instruction="English def", field_type="text", auto_fill=False
        )
        assert fi.instruction == "English def"
        assert fi.field_type == "text"
        assert fi.auto_fill is False


class TestGeneralSettings:
    def test_defaults(self) -> None:
        gs = GeneralSettings()
        assert gs.fill_all_shortcut == "Ctrl+Shift+G"
        assert gs.fill_field_shortcut == "Ctrl+Shift+F"
        assert gs.default_user_prompt == ""
        assert gs.show_fill_dialog is True


class TestProviderConfig:
    def test_defaults(self) -> None:
        pc = ProviderConfig()
        assert pc.provider_type == ""
        assert pc.api_url == ""
        assert pc.api_key == ""
        assert pc.max_tokens == 4096
        assert pc.tts_model == ""
        assert pc.image_model == ""

    def test_custom_values(self) -> None:
        pc = ProviderConfig(
            provider_type="openai",
            api_url="https://api.openai.com/v1",
            api_key="sk-test",
            text_model="gpt-4o",
            max_tokens=2048,
        )
        assert pc.provider_type == "openai"
        assert pc.text_model == "gpt-4o"
        assert pc.max_tokens == 2048
