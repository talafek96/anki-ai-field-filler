"""Tests for ConfigManager dataclasses and config logic."""

from __future__ import annotations

import copy
from unittest.mock import MagicMock

import aqt

from ai_field_filler.config_manager import (
    FIELD_TYPES,
    ConfigManager,
    FieldInstruction,
    GeneralSettings,
    ProviderConfig,
)


# ---------------------------------------------------------------------------
# Dataclass tests
# ---------------------------------------------------------------------------


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

    def test_base_url_strips_trailing_slash(self) -> None:
        pc = ProviderConfig(api_url="https://api.openai.com/v1/")
        assert pc.base_url == "https://api.openai.com/v1"

    def test_base_url_no_slash(self) -> None:
        pc = ProviderConfig(api_url="https://api.openai.com/v1")
        assert pc.base_url == "https://api.openai.com/v1"

    def test_base_url_multiple_slashes(self) -> None:
        pc = ProviderConfig(api_url="https://api.openai.com/v1///")
        assert pc.base_url == "https://api.openai.com/v1"


class TestFieldTypes:
    def test_field_types_tuple(self) -> None:
        assert FIELD_TYPES == ("auto", "text", "audio", "image")


# ---------------------------------------------------------------------------
# ConfigManager tests (mocked Anki addon manager)
# ---------------------------------------------------------------------------

_SAMPLE_CONFIG = {
    "providers": {
        "openai": {
            "api_url": "https://api.openai.com/v1",
            "api_key": "sk-test",
            "text_model": "gpt-4o",
            "max_tokens": 4096,
            "tts_model": "tts-1",
            "tts_voice": "alloy",
            "image_model": "dall-e-3",
        },
        "anthropic": {
            "api_url": "https://api.anthropic.com/v1",
            "api_key": "ant-key",
            "text_model": "claude-sonnet-4-20250514",
            "max_tokens": 4096,
        },
    },
    "active_providers": {
        "text": "openai",
        "tts": "openai",
        "image": "openai",
    },
    "note_type_field_instructions": {
        "Basic": {
            "Back": {
                "instruction": "Answer to the front",
                "field_type": "text",
                "auto_fill": True,
            }
        }
    },
    "general": {
        "fill_all_shortcut": "Ctrl+Shift+G",
        "fill_field_shortcut": "Ctrl+Shift+F",
        "default_user_prompt": "",
        "show_fill_dialog": True,
    },
}


def _make_config_manager(config: dict | None = None, defaults: dict | None = None):
    """Create a ConfigManager with mocked Anki addon manager."""
    # Reset singleton
    ConfigManager._instance = None

    cfg_data = copy.deepcopy(config if config is not None else _SAMPLE_CONFIG)
    def_data = copy.deepcopy(defaults if defaults is not None else _SAMPLE_CONFIG)

    mock_addon_mgr = MagicMock()
    mock_addon_mgr.addonFromModule.return_value = "ai_field_filler"
    mock_addon_mgr.getConfig.return_value = cfg_data
    mock_addon_mgr.addonConfigDefaults.return_value = def_data

    aqt.mw.addonManager = mock_addon_mgr

    cm = ConfigManager()
    return cm, mock_addon_mgr


class TestConfigManagerProviders:
    def test_get_provider_config(self) -> None:
        cm, _ = _make_config_manager()
        cfg = cm.get_provider_config("openai")
        assert cfg.provider_type == "openai"
        assert cfg.api_url == "https://api.openai.com/v1"
        assert cfg.api_key == "sk-test"
        assert cfg.text_model == "gpt-4o"
        assert cfg.tts_model == "tts-1"

    def test_get_provider_config_unknown_returns_empty(self) -> None:
        cm, _ = _make_config_manager()
        cfg = cm.get_provider_config("nonexistent")
        assert cfg.provider_type == "nonexistent"
        assert cfg.api_url == ""

    def test_set_provider_config(self) -> None:
        cm, _ = _make_config_manager()
        new_cfg = ProviderConfig(
            provider_type="openai",
            api_url="https://custom.url",
            api_key="new-key",
            text_model="gpt-5",
            max_tokens=8192,
        )
        cm.set_provider_config("openai", new_cfg)
        result = cm.get_provider_config("openai")
        assert result.api_url == "https://custom.url"
        assert result.text_model == "gpt-5"
        assert result.max_tokens == 8192

    def test_get_all_provider_types(self) -> None:
        cm, _ = _make_config_manager()
        types = cm.get_all_provider_types()
        assert "openai" in types
        assert "anthropic" in types


class TestConfigManagerActiveProviders:
    def test_get_active_provider_type(self) -> None:
        cm, _ = _make_config_manager()
        assert cm.get_active_provider_type("text") == "openai"
        assert cm.get_active_provider_type("tts") == "openai"

    def test_get_active_provider_type_default(self) -> None:
        cm, _ = _make_config_manager(config={})
        assert cm.get_active_provider_type("text") == "openai"

    def test_set_active_provider_type(self) -> None:
        cm, _ = _make_config_manager()
        cm.set_active_provider_type("text", "anthropic")
        assert cm.get_active_provider_type("text") == "anthropic"

    def test_get_active_text_provider(self) -> None:
        cm, _ = _make_config_manager()
        cfg = cm.get_active_text_provider()
        assert cfg.provider_type == "openai"
        assert cfg.text_model == "gpt-4o"

    def test_get_active_tts_provider_disabled(self) -> None:
        config = dict(_SAMPLE_CONFIG)
        config["active_providers"] = {"text": "openai", "tts": "disabled", "image": "openai"}
        cm, _ = _make_config_manager(config=config)
        assert cm.get_active_tts_provider() is None

    def test_get_active_tts_provider_no_model(self) -> None:
        config = dict(_SAMPLE_CONFIG)
        config["providers"] = dict(config["providers"])
        config["providers"]["openai"] = dict(config["providers"]["openai"])
        config["providers"]["openai"]["tts_model"] = ""
        cm, _ = _make_config_manager(config=config)
        assert cm.get_active_tts_provider() is None

    def test_get_active_image_provider_disabled(self) -> None:
        config = dict(_SAMPLE_CONFIG)
        config["active_providers"] = {"text": "openai", "tts": "openai", "image": "disabled"}
        cm, _ = _make_config_manager(config=config)
        assert cm.get_active_image_provider() is None


class TestConfigManagerFieldInstructions:
    def test_get_field_instructions(self) -> None:
        cm, _ = _make_config_manager()
        instrs = cm.get_field_instructions("Basic")
        assert "Back" in instrs
        assert instrs["Back"].instruction == "Answer to the front"
        assert instrs["Back"].field_type == "text"
        assert instrs["Back"].auto_fill is True

    def test_get_field_instructions_unknown_note_type(self) -> None:
        cm, _ = _make_config_manager()
        instrs = cm.get_field_instructions("NonExistent")
        assert instrs == {}

    def test_set_field_instruction(self) -> None:
        cm, _ = _make_config_manager()
        cm.set_field_instruction(
            "Basic", "Front",
            FieldInstruction(instruction="Question", field_type="text"),
        )
        instrs = cm.get_field_instructions("Basic")
        assert "Front" in instrs
        assert instrs["Front"].instruction == "Question"

    def test_remove_field_instruction(self) -> None:
        cm, _ = _make_config_manager()
        cm.remove_field_instruction("Basic", "Back")
        instrs = cm.get_field_instructions("Basic")
        assert "Back" not in instrs

    def test_remove_field_instruction_cleans_empty_note_type(self) -> None:
        cm, _ = _make_config_manager()
        cm.remove_field_instruction("Basic", "Back")
        # After removing the only field, the note type entry should be gone
        nt_instr = cm._config.get("note_type_field_instructions", {})
        assert "Basic" not in nt_instr


class TestConfigManagerGeneralSettings:
    def test_get_general_settings(self) -> None:
        cm, _ = _make_config_manager()
        gs = cm.get_general_settings()
        assert gs.fill_all_shortcut == "Ctrl+Shift+G"
        assert gs.fill_field_shortcut == "Ctrl+Shift+F"
        assert gs.show_fill_dialog is True

    def test_set_general_settings(self) -> None:
        cm, _ = _make_config_manager()
        cm.set_general_settings(GeneralSettings(
            fill_all_shortcut="Ctrl+G",
            fill_field_shortcut="Ctrl+F",
            default_user_prompt="Be concise",
            show_fill_dialog=False,
        ))
        gs = cm.get_general_settings()
        assert gs.fill_all_shortcut == "Ctrl+G"
        assert gs.default_user_prompt == "Be concise"
        assert gs.show_fill_dialog is False


class TestConfigManagerWrite:
    def test_write_calls_addon_manager(self) -> None:
        cm, mock_mgr = _make_config_manager()
        cm.write()
        mock_mgr.writeConfig.assert_called_once()

    def test_update_from_addon_manager(self) -> None:
        cm, _ = _make_config_manager()
        cm.update_from_addon_manager({"general": {"fill_all_shortcut": "Alt+G"}})
        gs = cm.get_general_settings()
        assert gs.fill_all_shortcut == "Alt+G"


class TestConfigManagerEnsureSection:
    def test_ensure_section_creates_missing(self) -> None:
        cm, _ = _make_config_manager(config={})
        cm._ensure_section("providers")
        assert "providers" in cm._config

    def test_ensure_section_preserves_existing(self) -> None:
        cm, _ = _make_config_manager()
        original = cm._config["providers"]
        cm._ensure_section("providers")
        assert cm._config["providers"] is original
