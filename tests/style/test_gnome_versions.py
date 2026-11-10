# SPDX-License-Identifier: GPL-2.0-or-later
"""Every GNOME major a page or a tool names is one metadata.json lists, and each line that
says which GNOME Scroll Zoom needs names every major it lists, so adding or dropping one in
shell-version finds each place to update (decision 0008). Decisions keep their history."""

import json
import re
from typing import cast

from tests.paths import EXTENSION, ROOT
from tests.style.test_words import tracked

METADATA: dict[str, object] = json.loads((EXTENSION / "metadata.json").read_text())
LISTED = {str(major) for major in cast("list[object]", METADATA["shell-version"])}
NAMED = re.compile(r"\bGNOME(?:\s+Shell)?\s+(\d{2,3})\b")
# The lines that tell a person which GNOME Scroll Zoom needs.
NEEDS = (
    ("README.md", re.compile(r"^GNOME .* on Wayland")),
    ("site/index.html", re.compile(r"You need <strong>GNOME")),
    ("site/index.html", re.compile(r'"operatingSystem"')),
    (".github/workflows/release.yml", re.compile(r"Needs GNOME")),
)


def unlisted_in(text: str, listed: set[str]) -> list[tuple[int, str]]:
    """The line and the major of each GNOME major the text names that is not among listed,
    a mention a line wrap splits included."""
    return [
        (text.count("\n", 0, m.start()) + 1, m.group(1))
        for m in NAMED.finditer(text)
        if m.group(1) not in listed
    ]


def unlisted(listed: set[str]) -> list[str]:
    """Each place outside docs/decisions/ that names a GNOME major not among listed."""
    return [
        f"{path}:{number}: GNOME {major}"
        for path in tracked()
        if not path.startswith("docs/decisions/")
        for number, major in unlisted_in((ROOT / path).read_text(), listed)
    ]


def unnamed(listed: set[str]) -> list[str]:
    """Each line that says which GNOME is needed and leaves out a major among listed."""
    found: list[str] = []
    for path, pattern in NEEDS:
        lines = [
            (number, line)
            for number, line in enumerate((ROOT / path).read_text().splitlines(), start=1)
            if pattern.search(line)
        ]
        if len(lines) != 1:
            found.append(f"{path}: one line matches {pattern.pattern!r}, not {len(lines)}")
            continue
        number, line = lines[0]
        if missing := [major for major in sorted(listed) if not re.search(rf"\b{major}\b", line)]:
            found.append(f"{path}:{number}: names no GNOME {', '.join(missing)}")
    return found


def test_each_gnome_major_named_is_one_metadata_lists() -> None:
    found = unlisted(LISTED)
    assert not found, "name a major metadata.json lists:\n" + "\n".join(found)


def test_each_line_that_says_which_gnome_is_needed_names_every_listed_major() -> None:
    found = unnamed(LISTED)
    assert not found, "name each major metadata.json lists:\n" + "\n".join(found)


def test_the_checks_find_a_major_dropped_or_added() -> None:
    assert unlisted(set()), "the README names the GNOME it needs"
    added = str(max(int(major) for major in LISTED) + 1)
    assert len(unnamed(LISTED | {added})) == len(NEEDS)


def test_a_mention_split_by_a_line_wrap_is_found() -> None:
    assert unlisted_in("Scroll Zoom runs on GNOME\n50 on Wayland", set()) == [(1, "50")]
