# SPDX-License-Identifier: GPL-2.0-or-later
"""No words that sell instead of saying, no tool or model names, no emoji."""

import re
import subprocess

from tests.paths import ROOT

BANNED = re.compile(
    r"\b(?:seamless(?:ly)?|robust|leverag\w*|comprehensive|blazing(?:ly)?|cutting-edge"
    r"|chatgpt|copilot|openai|anthropic|gemini|llm|ai-generated)\b",
    re.IGNORECASE,
)
# The agent tooling's own file and folder names are paths, not mentions.
PATHS = re.compile(r"CLAUDE\.md|\.claude/")
TOOL = re.compile(r"\bclaude\b", re.IGNORECASE)
EMOJI = re.compile("[\U0001f300-\U0001faff☀-➿]")
# The tests of the bans themselves spell out what they ban.
BAN_TESTS = {"tests/style/test_words.py", "tests/unit/test_commits.py"}
TEXT = (
    ".html",
    ".md",
    ".js",
    ".py",
    ".feature",
    ".sh",
    ".xml",
    ".json",
    ".toml",
    ".yml",
    "Makefile",
)


def tracked_paths() -> list[str]:
    """Every file git tracks or would track, so nothing ignored or generated is read."""
    out = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    return [p for p in out.splitlines() if (ROOT / p).exists()]


def tracked() -> list[str]:
    """The text files among them, but for the tests of the bans themselves."""
    return [p for p in tracked_paths() if p.endswith(TEXT) and p not in BAN_TESTS]


def test_no_banned_words_tool_names_or_emoji() -> None:
    found: list[str] = []
    for path in tracked():
        for number, line in enumerate((ROOT / path).read_text().splitlines(), start=1):
            bare = PATHS.sub("", line)
            for pattern in (BANNED, TOOL, EMOJI):
                for match in pattern.finditer(bare):
                    found.append(f"{path}:{number}: {match.group(0)!r}")
    assert not found, "\n".join(found)
