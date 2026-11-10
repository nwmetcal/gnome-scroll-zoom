# SPDX-License-Identifier: GPL-2.0-or-later
"""AGENTS.md names only make targets that exist, and maps every top-level folder."""

import re

from tests.paths import ROOT

AGENTS = (ROOT / "AGENTS.md").read_text()
TARGETS = set(re.findall(r"^([a-z][a-z-]*):", (ROOT / "Makefile").read_text(), re.M))
# Folders git does not track, or that only tools make.
UNTRACKED = {".git", ".venv", "build", ".ruff_cache", ".pytest_cache", "__pycache__"}


def test_every_make_target_agents_md_names_exists() -> None:
    named = set(re.findall(r"`make ([a-z][a-z-]*)", AGENTS))
    assert named, "AGENTS.md names no make targets"
    assert named <= TARGETS, f"not in the Makefile: {sorted(named - TARGETS)}"


def test_the_code_map_names_every_top_level_folder() -> None:
    folders = {p.name for p in ROOT.iterdir() if p.is_dir() and p.name not in UNTRACKED}
    missing = [name for name in sorted(folders) if f"`{name}/`" not in AGENTS]
    assert not missing, f"AGENTS.md's code map leaves out {missing}"
