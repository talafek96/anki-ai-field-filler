"""Tests for Config dataclasses and config logic."""

from __future__ import annotations

import copy
from src.core.config import (
    FIELD_TYPES,
    Config,
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
        fi = FieldInstruction(instruction="English def", field_type="text", auto_fill=False)
        assert fi.instruction == "English def"
        assert fi.field_type == "text"
        assert fi.auto_fill is False


class TestGeneralSettings:
    def test_defaults(self) -> None:
        gs = GeneralSettings()
        assert gs.fill_all_shortcut == "Ctrl+Shift+G"
        assert gs.fill_all_prompt == ""


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
        assert FIELD_TYPES == ("auto", "text", "audio", "image", "rich")


# ---------------------------------------------------------------------------
# Config tests (mocked Anki addon manager)
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


class TestConfigProviders:
    def test_get_provider_config(self, mock_config) -> None:
        cm, _ = mock_config(_SAMPLE_CONFIG)
        cfg = cm.get_provider_config("openai")
        assert cfg.provider_type == "openai"
        assert cfg.api_url == "https://api.openai.com/v1"
        assert cfg.api_key == "sk-test"
        assert cfg.text_model == "gpt-4o"
        assert cfg.tts_model == "tts-1"

    def test_get_provider_config_unknown_returns_empty(self, mock_config) -> None:
        cm, _ = mock_config(_SAMPLE_CONFIG)
        cfg = cm.get_provider_config("nonexistent")
        assert cfg.provider_type == "nonexistent"
        assert cfg.api_url == ""

    def test_set_provider_config(self, mock_config) -> None:
        cm, _ = mock_config(_SAMPLE_CONFIG)
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

    def test_get_all_provider_types(self, mock_config) -> None:
        cm, _ = mock_config(_SAMPLE_CONFIG)
        types = cm.get_all_provider_types()
        assert "openai" in types
        assert "anthropic" in types


class TestConfigActiveProviders:
    def test_get_active_provider_type(self, mock_config) -> None:
        cm, _ = mock_config(_SAMPLE_CONFIG)
        assert cm.get_active_provider_type("text") == "openai"
        assert cm.get_active_provider_type("tts") == "openai"

    def test_get_active_provider_type_default(self, mock_config) -> None:
        cm, _ = mock_config({})
        assert cm.get_active_provider_type("text") == "openai"

    def test_set_active_provider_type(self, mock_config) -> None:
        cm, _ = mock_config(_SAMPLE_CONFIG)
        cm.set_active_provider_type("text", "anthropic")
        assert cm.get_active_provider_type("text") == "anthropic"

    def test_get_active_text_provider(self, mock_config) -> None:
        cm, _ = mock_config(_SAMPLE_CONFIG)
        cfg = cm.get_active_text_provider()
        assert cfg.provider_type == "openai"
        assert cfg.text_model == "gpt-4o"

    def test_get_active_tts_provider_disabled(self, mock_config) -> None:
        config = dict(_SAMPLE_CONFIG)
        config["active_providers"] = {"text": "openai", "tts": "disabled", "image": "openai"}
        cm, _ = mock_config(config)
        assert cm.get_active_tts_provider() is None

    def test_get_active_tts_provider_no_model(self, mock_config) -> None:
        config = copy.deepcopy(_SAMPLE_CONFIG)
        config["providers"]["openai"]["tts_model"] = ""
        cm, _ = mock_config(config)
        assert cm.get_active_tts_provider() is None

    def test_get_active_image_provider_disabled(self, mock_config) -> None:
        config = dict(_SAMPLE_CONFIG)
        config["active_providers"] = {"text": "openai", "tts": "openai", "image": "disabled"}
        cm, _ = mock_config(config)
        assert cm.get_active_image_provider() is None


class TestConfigFieldInstructions:
    def test_get_field_instructions(self, mock_config) -> None:
        cm, _ = mock_config(_SAMPLE_CONFIG)
        instrs = cm.get_field_instructions("Basic")
        assert "Back" in instrs
        assert instrs["Back"].instruction == "Answer to the front"
        assert instrs["Back"].field_type == "text"
        assert instrs["Back"].auto_fill is True

    def test_get_field_instructions_unknown_note_type(self, mock_config) -> None:
        cm, _ = mock_config(_SAMPLE_CONFIG)
        instrs = cm.get_field_instructions("NonExistent")
        assert instrs == {}

    def test_set_field_instruction(self, mock_config) -> None:
        cm, _ = mock_config(_SAMPLE_CONFIG)
        cm.set_field_instruction(
            "Basic",
            "Front",
            FieldInstruction(instruction="Question", field_type="text"),
        )
        instrs = cm.get_field_instructions("Basic")
        assert "Front" in instrs
        assert instrs["Front"].instruction == "Question"

    def test_remove_field_instruction(self, mock_config) -> None:
        cm, _ = mock_config(_SAMPLE_CONFIG)
        cm.remove_field_instruction("Basic", "Back")
        instrs = cm.get_field_instructions("Basic")
        assert "Back" not in instrs

    def test_remove_field_instruction_cleans_empty_note_type(self, mock_config) -> None:
        cm, _ = mock_config(_SAMPLE_CONFIG)
        cm.remove_field_instruction("Basic", "Back")
        # After removing the only field, the note type entry should be gone
        nt_instr = cm._config.get("note_type_field_instructions", {})
        assert "Basic" not in nt_instr


class TestConfigGeneralSettings:
    def test_get_general_settings(self, mock_config) -> None:
        cm, _ = mock_config(_SAMPLE_CONFIG)
        gs = cm.get_general_settings()
        assert gs.fill_all_shortcut == "Ctrl+Shift+G"
        assert gs.last_configured_provider == "openai"

    def test_set_general_settings(self, mock_config) -> None:
        cm, _ = mock_config(_SAMPLE_CONFIG)
        cm.set_general_settings(
            GeneralSettings(
                fill_all_shortcut="Ctrl+G",
                fill_all_prompt="Be concise",
                last_configured_provider="google",
            )
        )
        gs = cm.get_general_settings()
        # Some attributes were flattened or removed from GeneralSettings
        assert gs.fill_all_shortcut == "Ctrl+G"
        assert gs.fill_all_prompt == "Be concise"
        assert gs.last_configured_provider == "google"


class TestConfigWrite:
    def test_write_calls_addon_manager(self, mock_config) -> None:
        cm, mock_mgr = mock_config(_SAMPLE_CONFIG)
        cm.write()
        mock_mgr.writeConfig.assert_called_once()

    def test_update_from_addon_manager(self, mock_config) -> None:
        cm, _ = mock_config(_SAMPLE_CONFIG)
        cm.update_from_addon_manager({"general": {"fill_all_shortcut": "Alt+G"}})
        gs = cm.get_general_settings()
        assert gs.fill_all_shortcut == "Alt+G"


class TestConfigEnsureSection:
    def test_ensure_section_creates_missing(self, mock_config) -> None:
        cm, _ = mock_config({})
        cm._ensure_section("providers")
        assert "providers" in cm._config

    def test_ensure_section_preserves_existing(self, mock_config) -> None:
        cm, _ = mock_config(_SAMPLE_CONFIG)
        original = cm._config["providers"]
        cm._ensure_section("providers")
        assert cm._config["providers"] is original


# ---------------------------------------------------------------------------
# Deck-scoped field instructions
# ---------------------------------------------------------------------------

_DECK_CONFIG = {
    **_SAMPLE_CONFIG,
    "deck_field_instructions": {
        "JLPT N3": {
            "Basic": {
                "Back": {
                    "instruction": "N3-level answer",
                    "field_type": "text",
                    "auto_fill": True,
                }
            }
        }
    },
}


class TestDeckFieldInstructions:
    def test_get_global_unaffected_by_deck_data(self, mock_config) -> None:
        cm, _ = mock_config(_DECK_CONFIG)
        instrs = cm.get_global_field_instructions("Basic")
        assert instrs["Back"].instruction == "Answer to the front"

    def test_get_deck_instructions(self, mock_config) -> None:
        cm, _ = mock_config(_DECK_CONFIG)
        instrs = cm.get_deck_field_instructions("JLPT N3", "Basic")
        assert instrs["Back"].instruction == "N3-level answer"

    def test_get_deck_instructions_empty_for_unknown_deck(self, mock_config) -> None:
        cm, _ = mock_config(_DECK_CONFIG)
        instrs = cm.get_deck_field_instructions("Unknown Deck", "Basic")
        assert instrs == {}

    def test_merged_without_deck_returns_global(self, mock_config) -> None:
        cm, _ = mock_config(_DECK_CONFIG)
        instrs = cm.get_field_instructions("Basic")
        assert instrs["Back"].instruction == "Answer to the front"

    def test_merged_with_deck_overrides_global(self, mock_config) -> None:
        cm, _ = mock_config(_DECK_CONFIG)
        instrs = cm.get_field_instructions("Basic", deck_name="JLPT N3")
        assert instrs["Back"].instruction == "N3-level answer"

    def test_merged_keeps_global_fields_not_in_deck(self, mock_config) -> None:
        """Fields only defined globally are preserved in the merge."""
        config = copy.deepcopy(_DECK_CONFIG)
        config["note_type_field_instructions"]["Basic"]["Front"] = {
            "instruction": "Global front",
            "field_type": "text",
            "auto_fill": True,
        }
        cm, _ = mock_config(config)
        instrs = cm.get_field_instructions("Basic", deck_name="JLPT N3")
        # Front is only global — should survive the merge
        assert instrs["Front"].instruction == "Global front"
        # Back is overridden by deck
        assert instrs["Back"].instruction == "N3-level answer"

    def test_set_deck_field_instruction(self, mock_config) -> None:
        cm, _ = mock_config(_SAMPLE_CONFIG)
        cm.set_deck_field_instruction(
            "MyDeck",
            "Basic",
            "Back",
            FieldInstruction(instruction="Deck-specific"),
        )
        instrs = cm.get_deck_field_instructions("MyDeck", "Basic")
        assert instrs["Back"].instruction == "Deck-specific"

    def test_set_field_instruction_with_deck_name(self, mock_config) -> None:
        cm, _ = mock_config(_SAMPLE_CONFIG)
        cm.set_field_instruction(
            "Basic",
            "Back",
            FieldInstruction(instruction="Via unified API"),
            deck_name="MyDeck",
        )
        instrs = cm.get_deck_field_instructions("MyDeck", "Basic")
        assert instrs["Back"].instruction == "Via unified API"
        # Global should be unchanged
        global_instrs = cm.get_global_field_instructions("Basic")
        assert global_instrs["Back"].instruction == "Answer to the front"

    def test_remove_deck_field_instruction(self, mock_config) -> None:
        cm, _ = mock_config(_DECK_CONFIG)
        cm.remove_deck_field_instruction("JLPT N3", "Basic", "Back")
        instrs = cm.get_deck_field_instructions("JLPT N3", "Basic")
        assert "Back" not in instrs

    def test_remove_deck_cleans_empty_parents(self, mock_config) -> None:
        cm, _ = mock_config(_DECK_CONFIG)
        cm.remove_deck_field_instruction("JLPT N3", "Basic", "Back")
        dfi = cm._config.get("deck_field_instructions", {})
        assert "JLPT N3" not in dfi

    def test_remove_field_instruction_with_deck_name(self, mock_config) -> None:
        cm, _ = mock_config(_DECK_CONFIG)
        cm.remove_field_instruction("Basic", "Back", deck_name="JLPT N3")
        instrs = cm.get_deck_field_instructions("JLPT N3", "Basic")
        assert "Back" not in instrs
        # Global should be untouched
        global_instrs = cm.get_global_field_instructions("Basic")
        assert "Back" in global_instrs


# ---------------------------------------------------------------------------
# Model cache tests
# ---------------------------------------------------------------------------


class TestModelCache:
    def test_empty_cache_returns_empty_list(self, mock_config) -> None:
        cm, _ = mock_config(_SAMPLE_CONFIG)
        assert cm.get_cached_models("openai", "text") == []

    def test_set_and_get_cached_models(self, mock_config) -> None:
        cm, _ = mock_config(_SAMPLE_CONFIG)
        models = ["gpt-4o", "gpt-5.4"]
        cm.set_cached_models("openai", "text", models)
        assert cm.get_cached_models("openai", "text") == models

    def test_multiple_capabilities(self, mock_config) -> None:
        cm, _ = mock_config(_SAMPLE_CONFIG)
        cm.set_cached_models("openai", "text", ["gpt-4o"])
        cm.set_cached_models("openai", "tts", ["tts-1"])
        cm.set_cached_models("openai", "image", ["dall-e-3"])
        assert cm.get_cached_models("openai", "text") == ["gpt-4o"]
        assert cm.get_cached_models("openai", "tts") == ["tts-1"]
        assert cm.get_cached_models("openai", "image") == ["dall-e-3"]

    def test_multiple_providers(self, mock_config) -> None:
        cm, _ = mock_config(_SAMPLE_CONFIG)
        cm.set_cached_models("openai", "text", ["gpt-4o"])
        cm.set_cached_models("google", "text", ["gemini-2.5-flash"])
        assert cm.get_cached_models("openai", "text") == ["gpt-4o"]
        assert cm.get_cached_models("google", "text") == ["gemini-2.5-flash"]

    def test_get_all_cached_models(self, mock_config) -> None:
        cm, _ = mock_config({}) # Empty config to start clean
        cm.set_cached_models("openai", "text", ["gpt-4o"])
        cm.set_cached_models("openai", "tts", ["tts-1"])
        result = cm.get_all_cached_models("openai")
        assert result["text"] == ["gpt-4o"]
        assert result["tts"] == ["tts-1"]

    def test_get_all_cached_models_unknown_provider(self, mock_config) -> None:
        cm, _ = mock_config(_SAMPLE_CONFIG)
        assert cm.get_all_cached_models("unknown") == {}

    def test_overwrite_existing_cache(self, mock_config) -> None:
        cm, _ = mock_config(_SAMPLE_CONFIG)
        cm.set_cached_models("openai", "text", ["gpt-4o"])
        cm.set_cached_models("openai", "text", ["gpt-5.4", "gpt-4o"])
        assert cm.get_cached_models("openai", "text") == ["gpt-5.4", "gpt-4o"]

    def test_cached_models_returns_copy(self, mock_config) -> None:
        cm, _ = mock_config(_SAMPLE_CONFIG)
        cm.set_cached_models("openai", "text", ["gpt-4o"])
        result = cm.get_cached_models("openai", "text")
        result.append("mutated")
        assert cm.get_cached_models("openai", "text") == ["gpt-4o"]

