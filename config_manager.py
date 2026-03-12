"""Configuration management for AI Field Filler addon."""

from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from aqt import mw


@dataclass
class ProviderConfig:
    """Configuration for a single AI provider."""

    provider_type: str = ""
    api_url: str = ""
    api_key: str = ""
    text_model: str = ""
    max_tokens: int = 4096
    tts_model: str = ""
    tts_voice: str = ""
    image_model: str = ""

    @property
    def base_url(self) -> str:
        """API URL with trailing slashes stripped."""
        return self.api_url.rstrip("/")


FIELD_TYPES = ("auto", "text", "audio", "image")
"""Valid values for :attr:`FieldInstruction.field_type`."""


@dataclass
class FieldInstruction:
    """Per-field instruction for AI context."""

    instruction: str = ""
    field_type: str = "auto"  # one of FIELD_TYPES
    auto_fill: bool = True


@dataclass
class GeneralSettings:
    """General addon settings."""

    fill_all_shortcut: str = "Ctrl+Shift+G"
    fill_field_shortcut: str = "Ctrl+Shift+F"
    default_user_prompt: str = ""
    show_fill_dialog: bool = True


class ConfigManager:
    """Singleton config manager wrapping Anki's addon config system.

    Provides typed access to provider configs, field instructions per note type,
    and general settings. Persist changes by calling write().
    """

    _instance: Optional[ConfigManager] = None
    _initialized: bool = False

    def __new__(cls) -> ConfigManager:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return
        self._initialized = True
        self._addon_name: str = mw.addonManager.addonFromModule(__name__)
        self._load()

    def _load(self) -> None:
        """Load config from Anki's addon manager."""
        self._config: Dict[str, Any] = mw.addonManager.getConfig(self._addon_name) or {}
        self._defaults: Dict[str, Any] = mw.addonManager.addonConfigDefaults(self._addon_name) or {}

    def _get(self, key: str, default: Any = None) -> Any:
        """Get a top-level config value, falling back to defaults."""
        return self._config.get(key, self._defaults.get(key, default))

    def write(self) -> None:
        """Persist config to disk."""
        mw.addonManager.writeConfig(self._addon_name, self._config)

    def _ensure_section(self, key: str) -> None:
        """Ensure a top-level config section exists (copied from defaults)."""
        if key not in self._config:
            self._config[key] = copy.deepcopy(self._defaults.get(key, {}))

    def update_from_addon_manager(self, new_config: Dict[str, Any]) -> None:
        """Called when user edits config via Anki's built-in JSON editor."""
        self._config.update(new_config)

    # --- Provider configuration ---

    def get_provider_config(self, provider_type: str) -> ProviderConfig:
        """Get config for a specific provider."""
        providers = self._get("providers", {})
        p = providers.get(provider_type, {})
        return ProviderConfig(
            provider_type=provider_type,
            api_url=p.get("api_url", ""),
            api_key=p.get("api_key", ""),
            text_model=p.get("text_model", ""),
            max_tokens=p.get("max_tokens", 4096),
            tts_model=p.get("tts_model", ""),
            tts_voice=p.get("tts_voice", ""),
            image_model=p.get("image_model", ""),
        )

    def set_provider_config(self, provider_type: str, config: ProviderConfig) -> None:
        """Set config for a specific provider."""
        self._ensure_section("providers")
        self._config["providers"][provider_type] = {
            "api_url": config.api_url,
            "api_key": config.api_key,
            "text_model": config.text_model,
            "max_tokens": config.max_tokens,
            "tts_model": config.tts_model,
            "tts_voice": config.tts_voice,
            "image_model": config.image_model,
        }

    def get_active_provider_type(self, capability: str = "text") -> str:
        """Get the active provider type for a capability (text/tts/image)."""
        active = self._get("active_providers", {})
        return active.get(capability, "openai")

    def set_active_provider_type(self, capability: str, provider_type: str) -> None:
        """Set the active provider type for a capability."""
        self._ensure_section("active_providers")
        self._config["active_providers"][capability] = provider_type

    def get_active_text_provider(self) -> ProviderConfig:
        """Get the active text generation provider config."""
        return self.get_provider_config(self.get_active_provider_type("text"))

    def get_active_tts_provider(self) -> Optional[ProviderConfig]:
        """Get the active TTS provider config, or None if disabled."""
        ptype = self.get_active_provider_type("tts")
        if ptype == "disabled":
            return None
        cfg = self.get_provider_config(ptype)
        return cfg if cfg.tts_model else None

    def get_active_image_provider(self) -> Optional[ProviderConfig]:
        """Get the active image provider config, or None if disabled."""
        ptype = self.get_active_provider_type("image")
        if ptype == "disabled":
            return None
        cfg = self.get_provider_config(ptype)
        return cfg if cfg.image_model else None

    def get_all_provider_types(self) -> List[str]:
        """Get all configured provider type names."""
        providers = self._get("providers", {})
        return list(providers.keys())

    # --- Field instructions ---

    @staticmethod
    def _parse_field_instructions(
        raw: Dict[str, Any],
    ) -> Dict[str, FieldInstruction]:
        """Parse a ``{field_name: data}`` dict into typed objects."""
        return {
            field_name: FieldInstruction(
                instruction=data.get("instruction", ""),
                field_type=data.get("field_type", "auto"),
                auto_fill=data.get("auto_fill", True),
            )
            for field_name, data in raw.items()
        }

    @staticmethod
    def _serialize_instruction(instruction: FieldInstruction) -> Dict[str, Any]:
        """Serialize a :class:`FieldInstruction` to a plain dict."""
        return {
            "instruction": instruction.instruction,
            "field_type": instruction.field_type,
            "auto_fill": instruction.auto_fill,
        }

    # -- global (note-type level) ----------------------------------------

    def get_global_field_instructions(self, note_type_name: str) -> Dict[str, FieldInstruction]:
        """Get the *global* field instructions for a note type (all decks)."""
        all_instr = self._get("note_type_field_instructions", {})
        return self._parse_field_instructions(all_instr.get(note_type_name, {}))

    # -- deck-scoped -----------------------------------------------------

    def get_deck_field_instructions(
        self, deck_name: str, note_type_name: str
    ) -> Dict[str, FieldInstruction]:
        """Get deck-specific instruction overrides (no merge with global)."""
        deck_instr = self._get("deck_field_instructions", {})
        per_deck = deck_instr.get(deck_name, {})
        return self._parse_field_instructions(per_deck.get(note_type_name, {}))

    def set_deck_field_instruction(
        self,
        deck_name: str,
        note_type_name: str,
        field_name: str,
        instruction: FieldInstruction,
    ) -> None:
        """Set a deck-specific instruction override for a single field."""
        if "deck_field_instructions" not in self._config:
            self._config["deck_field_instructions"] = {}
        dfi = self._config["deck_field_instructions"]
        if deck_name not in dfi:
            dfi[deck_name] = {}
        if note_type_name not in dfi[deck_name]:
            dfi[deck_name][note_type_name] = {}
        dfi[deck_name][note_type_name][field_name] = self._serialize_instruction(instruction)

    def remove_deck_field_instruction(
        self, deck_name: str, note_type_name: str, field_name: str
    ) -> None:
        """Remove a deck-specific instruction override."""
        dfi = self._config.get("deck_field_instructions", {})
        per_deck = dfi.get(deck_name, {})
        per_nt = per_deck.get(note_type_name, {})
        if field_name in per_nt:
            del per_nt[field_name]
            if not per_nt:
                del per_deck[note_type_name]
            if not per_deck:
                del dfi[deck_name]

    # -- merged (used at fill time) --------------------------------------

    def get_field_instructions(
        self, note_type_name: str, deck_name: Optional[str] = None
    ) -> Dict[str, FieldInstruction]:
        """Get effective field instructions, merging global + deck overrides.

        Deck-specific instructions override global ones per-field.
        Fields only defined globally are kept as-is.
        """
        result = self.get_global_field_instructions(note_type_name)
        if deck_name:
            overrides = self.get_deck_field_instructions(deck_name, note_type_name)
            result.update(overrides)
        return result

    def set_field_instruction(
        self,
        note_type_name: str,
        field_name: str,
        instruction: FieldInstruction,
        deck_name: Optional[str] = None,
    ) -> None:
        """Set instruction for a single field.

        When *deck_name* is ``None`` the instruction is stored globally;
        otherwise it is stored as a deck-specific override.
        """
        if deck_name:
            self.set_deck_field_instruction(deck_name, note_type_name, field_name, instruction)
            return
        if "note_type_field_instructions" not in self._config:
            self._config["note_type_field_instructions"] = {}
        nt = self._config["note_type_field_instructions"]
        if note_type_name not in nt:
            nt[note_type_name] = {}
        nt[note_type_name][field_name] = self._serialize_instruction(instruction)

    def remove_field_instruction(
        self,
        note_type_name: str,
        field_name: str,
        deck_name: Optional[str] = None,
    ) -> None:
        """Remove instruction for a specific field."""
        if deck_name:
            self.remove_deck_field_instruction(deck_name, note_type_name, field_name)
            return
        nt_instr = self._config.get("note_type_field_instructions", {})
        if note_type_name in nt_instr and field_name in nt_instr[note_type_name]:
            del nt_instr[note_type_name][field_name]
            if not nt_instr[note_type_name]:
                del nt_instr[note_type_name]

    # --- General settings ---

    def get_general_settings(self) -> GeneralSettings:
        """Get general addon settings."""
        g = self._get("general", {})
        return GeneralSettings(
            fill_all_shortcut=g.get("fill_all_shortcut", "Ctrl+Shift+G"),
            fill_field_shortcut=g.get("fill_field_shortcut", "Ctrl+Shift+F"),
            default_user_prompt=g.get("default_user_prompt", ""),
            show_fill_dialog=g.get("show_fill_dialog", True),
        )

    def set_general_settings(self, settings: GeneralSettings) -> None:
        """Set general addon settings."""
        self._config["general"] = {
            "fill_all_shortcut": settings.fill_all_shortcut,
            "fill_field_shortcut": settings.fill_field_shortcut,
            "default_user_prompt": settings.default_user_prompt,
            "show_fill_dialog": settings.show_fill_dialog,
        }
