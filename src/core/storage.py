"""Export / import addon settings to a portable JSON file.

API keys are optionally encrypted with a user-provided password using
PBKDF2-HMAC-SHA256 key derivation and a XOR stream cipher (stdlib only,
no external crypto dependencies).
"""

from __future__ import annotations

import base64
import copy
import hashlib
import json
import os
from typing import Any, Dict, Optional

from .config import EXPORTABLE_KEYS

# -- constants ---------------------------------------------------------------

_FORMAT_TAG = "ai-field-filler-settings"
_FORMAT_VERSION = 1
_VERIFY_PLAINTEXT = "AI_FIELD_FILLER_VERIFY_OK"
_PBKDF2_ITERATIONS = 100_000
_SALT_BYTES = 16


# -- encryption helpers (stdlib only) ----------------------------------------


def _derive_key(password: str, salt: bytes, length: int, context: str = "") -> bytes:
    """Derive *length* key bytes from *password* + *salt* via PBKDF2.

    An optional *context* string (e.g. the provider name) is appended to
    the salt so that each usage site produces a unique key-stream.
    """
    effective_salt = salt + context.encode("utf-8")
    return hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        effective_salt,
        _PBKDF2_ITERATIONS,
        dklen=length,
    )


def _xor_bytes(data: bytes, key: bytes) -> bytes:
    return bytes(a ^ b for a, b in zip(data, key))


def _encrypt_value(plaintext: str, password: str, salt: bytes, context: str) -> str:
    """Encrypt *plaintext* and return a Base64 string."""
    data = plaintext.encode("utf-8")
    if not data:
        return ""
    key = _derive_key(password, salt, len(data), context)
    return base64.b64encode(_xor_bytes(data, key)).decode("ascii")


def _decrypt_value(ciphertext: str, password: str, salt: bytes, context: str) -> str:
    """Decrypt a Base64 *ciphertext* back to a string.

    Raises :class:`ValueError` if the decrypted bytes are not valid UTF-8
    (typically means the password was wrong).
    """
    if not ciphertext:
        return ""
    data = base64.b64decode(ciphertext)
    key = _derive_key(password, salt, len(data), context)
    raw = _xor_bytes(data, key)
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        raise ValueError("Decryption produced invalid data (wrong password?)")


# -- API-key encryption/decryption in config dicts --------------------------


def _encrypt_api_keys(config: Dict[str, Any], password: str, salt: bytes) -> Dict[str, Any]:
    """Return a *copy* of *config* with all ``api_key`` values encrypted."""
    config = copy.deepcopy(config)
    providers = config.get("providers", {})
    for ptype, pdata in providers.items():
        raw_key = pdata.get("api_key", "")
        if raw_key:
            pdata["api_key"] = _encrypt_value(raw_key, password, salt, ptype)
    return config


def _decrypt_api_keys(config: Dict[str, Any], password: str, salt: bytes) -> Dict[str, Any]:
    """Return a *copy* of *config* with all ``api_key`` values decrypted."""
    config = copy.deepcopy(config)
    providers = config.get("providers", {})
    for ptype, pdata in providers.items():
        enc_key = pdata.get("api_key", "")
        if enc_key:
            pdata["api_key"] = _decrypt_value(enc_key, password, salt, ptype)
    return config


# -- public API --------------------------------------------------------------


class SettingsIOError(Exception):
    """Raised on format / validation / password errors during import."""


def export_settings(
    config: Dict[str, Any],
    path: str,
    password: Optional[str] = None,
) -> None:
    """Write addon settings to *path* as a JSON file.

    If *password* is provided (non-empty), API keys are encrypted.
    """
    payload: Dict[str, Any] = {
        "_format": _FORMAT_TAG,
        "_version": _FORMAT_VERSION,
    }

    if password:
        salt = os.urandom(_SALT_BYTES)
        payload["_encrypted"] = True
        payload["_salt"] = salt.hex()
        payload["_verify"] = _encrypt_value(_VERIFY_PLAINTEXT, password, salt, "__verify__")
        config = _encrypt_api_keys(config, password, salt)
    else:
        payload["_encrypted"] = False

    for key in EXPORTABLE_KEYS:
        if key in config:
            payload[key] = copy.deepcopy(config[key])

    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, ensure_ascii=False)


def import_settings(
    path: str,
    password: Optional[str] = None,
) -> Dict[str, Any]:
    """Read and validate a settings file, returning the config dict.

    Raises :class:`SettingsIOError` on any validation or decryption failure.
    """
    try:
        with open(path, "r", encoding="utf-8") as fh:
            payload = json.load(fh)
    except json.JSONDecodeError as exc:
        raise SettingsIOError(f"The file is not valid JSON:\n{exc}") from exc
    except OSError as exc:
        raise SettingsIOError(f"Could not read file:\n{exc}") from exc

    # -- format validation ---------------------------------------------------
    if not isinstance(payload, dict):
        raise SettingsIOError("Invalid settings file: expected a JSON object.")

    if payload.get("_format") != _FORMAT_TAG:
        raise SettingsIOError("This file does not appear to be an AI Filler settings export.")

    version = payload.get("_version", 0)
    if not isinstance(version, int) or version < 1:
        raise SettingsIOError("Unrecognised settings file version.")
    if version > _FORMAT_VERSION:
        raise SettingsIOError(
            f"This file was created by a newer version of the addon "
            f"(file version {version}, supported up to {_FORMAT_VERSION}).\n"
            f"Please update AI Filler and try again."
        )

    # -- decryption ----------------------------------------------------------
    encrypted = payload.get("_encrypted", False)
    if encrypted:
        salt_hex = payload.get("_salt")
        if not isinstance(salt_hex, str) or len(salt_hex) != _SALT_BYTES * 2:
            raise SettingsIOError("Settings file is corrupt (invalid salt).")
        salt = bytes.fromhex(salt_hex)

        if not password:
            raise SettingsIOError("This settings file is encrypted. Please provide the password.")

        # Verify password
        verify_token = payload.get("_verify", "")
        try:
            decrypted_verify = _decrypt_value(verify_token, password, salt, "__verify__")
        except Exception:
            raise SettingsIOError("Incorrect password or corrupt file.")
        if decrypted_verify != _VERIFY_PLAINTEXT:
            raise SettingsIOError("Incorrect password.")

    # -- extract config sections ---------------------------------------------
    config: Dict[str, Any] = {}
    for key in EXPORTABLE_KEYS:
        if key in payload:
            config[key] = copy.deepcopy(payload[key])

    if encrypted:
        assert password is not None  # validated above
        config = _decrypt_api_keys(config, password, salt)  # type: ignore[possibly-undefined]

    # -- basic structural validation -----------------------------------------
    providers = config.get("providers")
    if providers is not None and not isinstance(providers, dict):
        raise SettingsIOError("Invalid settings file: 'providers' must be an object.")

    active = config.get("active_providers")
    if active is not None and not isinstance(active, dict):
        raise SettingsIOError("Invalid settings file: 'active_providers' must be an object.")

    instructions = config.get("note_type_field_instructions")
    if instructions is not None and not isinstance(instructions, dict):
        raise SettingsIOError("Invalid settings file: 'note_type_field_instructions' must be an object.")

    general = config.get("general")
    if general is not None and not isinstance(general, dict):
        raise SettingsIOError("Invalid settings file: 'general' must be an object.")

    return config
