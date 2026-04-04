"""Tests for settings export / import (storage module + Config)."""

from __future__ import annotations

import copy
import json
import os

import pytest

from src.core.storage import (
    SettingsIOError,
    _decrypt_value,
    _encrypt_value,
    export_settings,
    import_settings,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SAMPLE_CONFIG = {
    "providers": {
        "openai": {
            "api_url": "https://api.openai.com/v1",
            "api_key": "sk-test-key-openai",
            "text_model": "gpt-4o",
            "max_tokens": 4096,
            "tts_model": "tts-1",
            "tts_voice": "alloy",
            "image_model": "dall-e-3",
        },
        "anthropic": {
            "api_url": "https://api.anthropic.com/v1",
            "api_key": "ant-key-secret",
            "text_model": "claude-sonnet-4-20250514",
            "max_tokens": 4096,
        },
        "google": {
            "api_url": "https://generativelanguage.googleapis.com/v1beta",
            "api_key": "",
            "text_model": "gemini-2.5-flash",
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
    "deck_field_instructions": {},
    "general": {
        "fill_all_shortcut": "Ctrl+Shift+G",
        "fill_field_shortcut": "Ctrl+Shift+F",
        "default_user_prompt": "",
        "show_fill_dialog": True,
    },
}


# ---------------------------------------------------------------------------
# Encryption helpers
# ---------------------------------------------------------------------------


class TestEncryptionHelpers:
    def test_roundtrip(self) -> None:
        salt = os.urandom(16)
        plaintext = "sk-my-secret-api-key-12345"
        encrypted = _encrypt_value(plaintext, "password123", salt, "openai")
        decrypted = _decrypt_value(encrypted, "password123", salt, "openai")
        assert decrypted == plaintext

    def test_empty_string_roundtrip(self) -> None:
        salt = os.urandom(16)
        assert _encrypt_value("", "pw", salt, "ctx") == ""
        assert _decrypt_value("", "pw", salt, "ctx") == ""

    def test_wrong_password_produces_different_output(self) -> None:
        salt = os.urandom(16)
        encrypted = _encrypt_value("real-key", "correct", salt, "openai")
        try:
            decrypted = _decrypt_value(encrypted, "wrong", salt, "openai")
            assert decrypted != "real-key"
        except ValueError:
            pass  # invalid UTF-8 from wrong password is expected

    def test_different_contexts_produce_different_ciphertexts(self) -> None:
        salt = os.urandom(16)
        enc1 = _encrypt_value("same-key", "pw", salt, "openai")
        enc2 = _encrypt_value("same-key", "pw", salt, "anthropic")
        assert enc1 != enc2

    def test_different_salts_produce_different_ciphertexts(self) -> None:
        enc1 = _encrypt_value("key", "pw", b"\x00" * 16, "ctx")
        enc2 = _encrypt_value("key", "pw", b"\x01" * 16, "ctx")
        assert enc1 != enc2

    def test_unicode_roundtrip(self) -> None:
        salt = os.urandom(16)
        plaintext = "api-key-with-unicode-\u00e9\u00e0\u00fc"
        encrypted = _encrypt_value(plaintext, "pw", salt, "ctx")
        decrypted = _decrypt_value(encrypted, "pw", salt, "ctx")
        assert decrypted == plaintext


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------


class TestExport:
    def test_export_without_encryption(self, tmp_path) -> None:
        path = str(tmp_path / "settings.aiff-settings")
        export_settings(_SAMPLE_CONFIG, path, password=None)

        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)

        assert data["_format"] == "ai-field-filler-settings"
        assert data["_version"] == 1
        assert data["_encrypted"] is False
        assert "_salt" not in data
        assert "_verify" not in data
        # API keys should be plaintext
        assert data["providers"]["openai"]["api_key"] == "sk-test-key-openai"
        assert data["providers"]["anthropic"]["api_key"] == "ant-key-secret"
        # Non-exportable keys should be absent
        assert "_model_cache" not in data

    def test_export_with_encryption(self, tmp_path) -> None:
        path = str(tmp_path / "settings.aiff-settings")
        export_settings(_SAMPLE_CONFIG, path, password="secret")

        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)

        assert data["_encrypted"] is True
        assert "_salt" in data
        assert "_verify" in data
        # API keys should NOT be plaintext
        assert data["providers"]["openai"]["api_key"] != "sk-test-key-openai"
        assert data["providers"]["openai"]["api_key"] != ""
        # Empty API key should remain empty
        assert data["providers"]["google"]["api_key"] == ""

    def test_export_preserves_instructions(self, tmp_path) -> None:
        path = str(tmp_path / "settings.aiff-settings")
        export_settings(_SAMPLE_CONFIG, path, password=None)

        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)

        assert (
            data["note_type_field_instructions"]["Basic"]["Back"]["instruction"]
            == "Answer to the front"
        )

    def test_export_does_not_mutate_input(self, tmp_path) -> None:
        config = copy.deepcopy(_SAMPLE_CONFIG)
        original_key = config["providers"]["openai"]["api_key"]
        export_settings(config, str(tmp_path / "out.aiff-settings"), password="pw")
        assert config["providers"]["openai"]["api_key"] == original_key

    def test_export_excludes_model_cache(self, tmp_path) -> None:
        config = copy.deepcopy(_SAMPLE_CONFIG)
        config["_model_cache"] = {"openai": {"text": ["gpt-4o"]}}
        path = str(tmp_path / "out.aiff-settings")
        export_settings(config, path)
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        assert "_model_cache" not in data


# ---------------------------------------------------------------------------
# Import
# ---------------------------------------------------------------------------


class TestImport:
    def test_roundtrip_no_encryption(self, tmp_path) -> None:
        path = str(tmp_path / "settings.aiff-settings")
        export_settings(_SAMPLE_CONFIG, path, password=None)
        result = import_settings(path, password=None)

        assert result["providers"]["openai"]["api_key"] == "sk-test-key-openai"
        assert result["active_providers"]["text"] == "openai"
        assert result["general"]["fill_all_shortcut"] == "Ctrl+Shift+G"

    def test_roundtrip_with_encryption(self, tmp_path) -> None:
        path = str(tmp_path / "settings.aiff-settings")
        export_settings(_SAMPLE_CONFIG, path, password="mypassword")
        result = import_settings(path, password="mypassword")

        assert result["providers"]["openai"]["api_key"] == "sk-test-key-openai"
        assert result["providers"]["anthropic"]["api_key"] == "ant-key-secret"
        assert result["providers"]["google"]["api_key"] == ""

    def test_wrong_password_raises(self, tmp_path) -> None:
        path = str(tmp_path / "settings.aiff-settings")
        export_settings(_SAMPLE_CONFIG, path, password="correct")
        with pytest.raises(SettingsIOError, match="Incorrect password"):
            import_settings(path, password="wrong")

    def test_encrypted_no_password_raises(self, tmp_path) -> None:
        path = str(tmp_path / "settings.aiff-settings")
        export_settings(_SAMPLE_CONFIG, path, password="pw")
        with pytest.raises(SettingsIOError, match="encrypted.*password"):
            import_settings(path, password=None)

    def test_invalid_json_raises(self, tmp_path) -> None:
        path = str(tmp_path / "bad.aiff-settings")
        with open(path, "w") as fh:
            fh.write("not json {{{")
        with pytest.raises(SettingsIOError, match="not valid JSON"):
            import_settings(path)

    def test_missing_format_tag_raises(self, tmp_path) -> None:
        path = str(tmp_path / "bad.aiff-settings")
        with open(path, "w") as fh:
            json.dump({"hello": "world"}, fh)
        with pytest.raises(SettingsIOError, match="does not appear"):
            import_settings(path)

    def test_future_version_raises(self, tmp_path) -> None:
        path = str(tmp_path / "future.aiff-settings")
        with open(path, "w") as fh:
            json.dump({"_format": "ai-field-filler-settings", "_version": 999}, fh)
        with pytest.raises(SettingsIOError, match="newer version"):
            import_settings(path)

    def test_corrupt_salt_raises(self, tmp_path) -> None:
        path = str(tmp_path / "bad.aiff-settings")
        with open(path, "w") as fh:
            json.dump(
                {
                    "_format": "ai-field-filler-settings",
                    "_version": 1,
                    "_encrypted": True,
                    "_salt": "short",
                },
                fh,
            )
        with pytest.raises(SettingsIOError, match="corrupt"):
            import_settings(path, password="pw")

    def test_not_a_dict_raises(self, tmp_path) -> None:
        path = str(tmp_path / "bad.aiff-settings")
        with open(path, "w") as fh:
            json.dump([1, 2, 3], fh)
        with pytest.raises(SettingsIOError, match="JSON object"):
            import_settings(path)

    def test_invalid_providers_type_raises(self, tmp_path) -> None:
        path = str(tmp_path / "bad.aiff-settings")
        with open(path, "w") as fh:
            json.dump(
                {
                    "_format": "ai-field-filler-settings",
                    "_version": 1,
                    "_encrypted": False,
                    "providers": "not a dict",
                },
                fh,
            )
        with pytest.raises(SettingsIOError, match="providers.*object"):
            import_settings(path)

    def test_file_not_found_raises(self, tmp_path) -> None:
        with pytest.raises(SettingsIOError, match="Could not read"):
            import_settings(str(tmp_path / "nonexistent.aiff-settings"))

    def test_partial_config_import(self, tmp_path) -> None:
        """Importing a file that only has 'general' should work."""
        path = str(tmp_path / "partial.aiff-settings")
        with open(path, "w") as fh:
            json.dump(
                {
                    "_format": "ai-field-filler-settings",
                    "_version": 1,
                    "_encrypted": False,
                    "general": {
                        "fill_all_shortcut": "Ctrl+G",
                        "fill_field_shortcut": "Ctrl+F",
                        "default_user_prompt": "be brief",
                        "show_fill_dialog": False,
                    },
                },
                fh,
            )
        result = import_settings(path)
        assert result["general"]["fill_all_shortcut"] == "Ctrl+G"
        assert "providers" not in result


# ---------------------------------------------------------------------------
# Config export / import methods
# ---------------------------------------------------------------------------


class TestConfigExportImport:
    def test_get_exportable_config_excludes_model_cache(self, mock_config) -> None:
        config = copy.deepcopy(_SAMPLE_CONFIG)
        config["_model_cache"] = {"openai": {"text": ["gpt-4o"]}}
        cm, _ = mock_config(raw_config=config)
        exported = cm.get_exportable_config()
        assert "_model_cache" not in exported
        assert "providers" in exported

    def test_get_exportable_config_returns_deep_copy(self, mock_config) -> None:
        cm, _ = mock_config(raw_config=_SAMPLE_CONFIG)
        exported = cm.get_exportable_config()
        exported["providers"]["openai"]["api_key"] = "mutated"
        assert cm.get_provider_config("openai").api_key == "sk-test-key-openai"

    def test_import_config_updates_live_config(self, mock_config) -> None:
        cm, _ = mock_config(raw_config=_SAMPLE_CONFIG)
        new_data = {
            "general": {
                "fill_all_shortcut": "Alt+G",
                "fill_all_prompt": "imported prompt",
                "last_configured_provider": "google",
            }
        }
        cm.import_config(new_data)
        gs = cm.get_general_settings()
        assert gs.fill_all_shortcut == "Alt+G"
        assert gs.fill_all_prompt == "imported prompt"
        assert gs.last_configured_provider == "google"

    def test_import_config_preserves_model_cache(self, mock_config) -> None:
        cm, _ = mock_config(raw_config=_SAMPLE_CONFIG)
        cm.set_cached_models("openai", "text", ["gpt-4o"])
        cm.import_config({"providers": _SAMPLE_CONFIG["providers"]})
        # Model cache should be untouched
        assert cm.get_cached_models("openai", "text") == ["gpt-4o"]

    def test_import_config_ignores_unknown_keys(self, mock_config) -> None:
        cm, _ = mock_config(raw_config=_SAMPLE_CONFIG)
        cm.import_config({"_model_cache": {"evil": {}}, "unknown_key": 42})
        # Just verify no crash and known keys are untouched
        assert cm.get_provider_config("openai").api_key == "sk-test-key-openai"

    def test_full_export_import_roundtrip(self, tmp_path, mock_config) -> None:
        cm, _ = mock_config(raw_config=_SAMPLE_CONFIG)
        exported = cm.get_exportable_config()
        path = str(tmp_path / "roundtrip.aiff-settings")
        export_settings(exported, path, password="test123")
        imported = import_settings(path, password="test123")
        cm.import_config(imported)

        cfg = cm.get_provider_config("openai")
        assert cfg.api_key == "sk-test-key-openai"
        assert cfg.text_model == "gpt-4o"
        gs = cm.get_general_settings()
        assert gs.fill_all_shortcut == "Ctrl+Shift+G"
