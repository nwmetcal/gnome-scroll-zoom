# SPDX-License-Identifier: GPL-2.0-or-later
"""The documents' prose keeps to 100 characters a line, as the Python does."""

import re
from collections.abc import Iterator

from tests.paths import ROOT
from tests.style.test_words import tracked_paths

WIDTH = 100
# The template fills a pull request's description, whose lines GitHub wraps for its reader.
UNWRAPPED = {".github/PULL_REQUEST_TEMPLATE.md"}
FENCE = re.compile(r"^\s*(?:```|~~~)")
# A link's target and a bare address cannot be wrapped; the link's words can.
TARGET = re.compile(r"\]\([^)\s]*\)|<?https?://\S+")
DEFINITION = re.compile(r"^\s*\[[^\]]+\]:\s")


def documents() -> list[str]:
    return [p for p in tracked_paths() if p.endswith(".md") and p not in UNWRAPPED]


def prose(text: str) -> Iterator[tuple[int, str]]:
    """Each line of prose and its number, as measured: front matter, fenced code, tables, images,
    and link definitions are not prose, and each link is measured without its target."""
    lines = text.splitlines()
    front = lines[:1] == ["---"]
    fenced = False
    for number, line in enumerate(lines, start=1):
        if front:
            front = number == 1 or line != "---"
            continue
        if FENCE.match(line):
            fenced = not fenced
            continue
        if fenced or line.lstrip().startswith(("|", "![")) or DEFINITION.match(line):
            continue
        yield number, TARGET.sub("]", line)


def too_long(text: str) -> list[int]:
    return [number for number, line in prose(text) if len(line) > WIDTH]


def test_a_prose_line_over_100_characters_is_too_long() -> None:
    assert too_long("x" * 100 + "\n" + "y" * 101) == [2]
    assert too_long("- " + "word " * 20 + "words") == [1]


def test_tables_code_images_links_and_front_matter_are_not_measured() -> None:
    long = "z" * 101
    assert too_long(f"---\ndescription: {long}\n---\n") == []
    assert too_long(f"| {long} | cell |") == []
    assert too_long(f"```text\n{long}\n```\n") == []
    assert too_long(f"![{long}](picture.png)") == []
    assert too_long(f"[the release](https://example.org/{long}) is out.") == []
    assert too_long(f"[release]: https://example.org/{long}") == []
    assert too_long(f"```\n```\n{long}") == [3]


def test_the_documents_prose_keeps_to_100_characters_a_line() -> None:
    assert documents()
    found = [
        f"{path}:{number}" for path in documents() for number in too_long((ROOT / path).read_text())
    ]
    assert not found, f"wrap these at {WIDTH} characters: {', '.join(found)}"
