#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""Package the AI Field Filler addon into a .ankiaddon file.

Standalone (stdlib-only) build script — run it via uv, no project install needed:
    uv run scripts/build_ankiaddon.py          # creates ai_field_filler.ankiaddon
    uv run scripts/build_ankiaddon.py --check  # dry-run: list files to be included
"""

from __future__ import annotations

import argparse
import os
import sys
import zipfile
from pathlib import Path

# The addon package is src/ai_field_filler/; its CONTENTS become the .ankiaddon
# root (where Anki expects __init__.py and config.json). Project tooling, tests,
# docs, and demo assets live above it in the repo and never ship.
REPO_ROOT = Path(__file__).resolve().parent.parent
ADDON_ROOT = REPO_ROOT / "src" / "ai_field_filler"

# Paths relative to the addon root that should NOT be in the package.
EXCLUDE_DIRS = {
    "__pycache__",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
}

EXCLUDE_FILES = {
    "meta.json",  # the user's live config, written by Anki at runtime
    "CLAUDE.md",  # nested agent context, not runtime
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
    return rel.suffix not in EXCLUDE_EXTENSIONS


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

    output = REPO_ROOT / OUTPUT_NAME
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
