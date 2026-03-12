#!/usr/bin/env python3
"""Package the AI Field Filler addon into a .ankiaddon file.

Usage:
    python build_ankiaddon.py          # creates ai_field_filler.ankiaddon
    python build_ankiaddon.py --check  # dry-run: list files that would be included
"""

from __future__ import annotations

import argparse
import os
import sys
import zipfile
from pathlib import Path

# Paths relative to the addon root that should NOT be in the package.
EXCLUDE_DIRS = {
    "__pycache__",
    ".git",
    ".github",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "tests",
    ".vscode",
    ".idea",
    "venv",
    "env",
    "node_modules",
}

EXCLUDE_FILES = {
    ".gitignore",
    "AGENTS.md",
    "build_ankiaddon.py",
    "ankiweb_listing.md",
    "pyproject.toml",
    "uv.lock",
    "meta.json",
    ".env",
    ".DS_Store",
    "Thumbs.db",
    "desktop.ini",
}

EXCLUDE_EXTENSIONS = {
    ".pyc",
    ".pyo",
    ".ankiaddon",
    ".swp",
    ".swo",
}

OUTPUT_NAME = "ai_field_filler.ankiaddon"

ADDON_ROOT = Path(__file__).resolve().parent


def should_include(path: Path) -> bool:
    """Return True if *path* belongs in the addon package."""
    rel = path.relative_to(ADDON_ROOT)
    parts = rel.parts

    # Skip excluded directories (and egg-info dirs)
    if any(p in EXCLUDE_DIRS or p.endswith(".egg-info") for p in parts):
        return False

    # Skip excluded files
    if rel.name in EXCLUDE_FILES:
        return False

    # Skip excluded extensions
    if rel.suffix in EXCLUDE_EXTENSIONS:
        return False

    return True


def collect_files() -> list[Path]:
    """Walk the addon tree and return all files to include."""
    files: list[Path] = []
    for root, dirs, filenames in os.walk(ADDON_ROOT):
        root_path = Path(root)
        # Prune excluded dirs in-place so os.walk skips them
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
        for fname in filenames:
            fpath = root_path / fname
            if should_include(fpath):
                files.append(fpath)
    return sorted(files)


def build(check: bool = False) -> None:
    files = collect_files()

    if not files:
        print("ERROR: No files to package!", file=sys.stderr)
        sys.exit(1)

    if check:
        print(f"Files that would be included ({len(files)}):\n")
        for f in files:
            print(f"  {f.relative_to(ADDON_ROOT)}")
        return

    output = ADDON_ROOT / OUTPUT_NAME
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as zf:
        for fpath in files:
            arcname = str(fpath.relative_to(ADDON_ROOT))
            zf.write(fpath, arcname)

    size_kb = output.stat().st_size / 1024
    print(f"Created {OUTPUT_NAME} ({size_kb:.1f} KB, {len(files)} files)")


def main() -> None:
    parser = argparse.ArgumentParser(description="Package AI Field Filler addon")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Dry-run: list files that would be included without creating the zip",
    )
    args = parser.parse_args()
    build(check=args.check)


if __name__ == "__main__":
    main()
