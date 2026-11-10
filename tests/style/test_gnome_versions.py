# SPDX-License-Identifier: GPL-2.0-or-later
"""Every GNOME major a page or a tool names is one metadata.json lists, and each place that
names one names every major it lists, so adding or dropping one in shell-version finds each
place to update (decision 0009). Decisions keep their history."""

import json
import re
from typing import cast

from tests.paths import EXTENSION, ROOT
from tests.style.test_words import tracked

METADATA: dict[str, object] = json.loads((EXTENSION / "metadata.json").read_text())
LISTED = {str(major) for major in cast("list[object]", METADATA["shell-version"])}
NAMED = re.compile(
    r"\bGNOME(?:\s+Shell)?\s+(\d{2,3}(?:(?:\s*,\s*|\s+)(?:(?:or|and|to)\s+)?\d{2,3})*)\b"
)
# This file names majors in its own cases.
ITSELF = "tests/style/test_gnome_versions.py"


def unlisted_in(text: str, listed: set[str]) -> list[tuple[int, str]]:
    """The line and the major of each GNOME major the text names that is not among listed,
    a mention a line wrap splits included."""
    return [
        (text.count("\n", 0, m.start()) + 1, major)
        for m in NAMED.finditer(text)
        for major in re.findall(r"\d{2,3}", m.group(1))
        if major not in listed
    ]


def unlisted(listed: set[str]) -> list[str]:
    """Each place outside docs/decisions/ that names a GNOME major not among listed."""
    return [
        f"{path}:{number}: GNOME {major}"
        for path in tracked()
        if not path.startswith("docs/decisions/") and path != ITSELF
        for number, major in unlisted_in((ROOT / path).read_text(), listed)
    ]


def unnamed(listed: set[str]) -> list[str]:
    """Each place outside docs/decisions/ that names a GNOME major and leaves out one among
    listed, read on the line of the mention and the next, which a wrap may carry it to."""
    found: list[str] = []
    for path in tracked():
        if path.startswith("docs/decisions/") or path == ITSELF:
            continue
        lines = (ROOT / path).read_text().splitlines()
        for number in sorted({n for n, _ in unlisted_in((ROOT / path).read_text(), set())}):
            near = " ".join(lines[number - 1 : number + 1])
            if missing := [m for m in sorted(listed) if not re.search(rf"\b{m}\b", near)]:
                found.append(f"{path}:{number}: names no GNOME {', '.join(missing)}")
    return found


def test_each_gnome_major_named_is_one_metadata_lists() -> None:
    found = unlisted(LISTED)
    assert not found, "name a major metadata.json lists:\n" + "\n".join(found)


def test_each_place_that_names_a_gnome_major_names_every_listed_major() -> None:
    found = unnamed(LISTED)
    assert not found, "name each major metadata.json lists:\n" + "\n".join(found)


def test_the_checks_find_a_major_dropped_or_added() -> None:
    dropped = {place.rsplit(": GNOME", 1)[0] for place in unlisted(set())}
    assert dropped, "the README names the GNOME it needs"
    added = str(max(int(major) for major in LISTED) + 1)
    named = {place.rsplit(": names no", 1)[0] for place in unnamed(LISTED | {added})}
    assert named == dropped, "each place that names one"


def test_a_mention_split_by_a_line_wrap_is_found() -> None:
    assert unlisted_in("Scroll Zoom runs on GNOME\n50 on Wayland", set()) == [(1, "50")]


def test_each_major_in_a_list_is_read() -> None:
    assert unlisted_in("GNOME 50 or 51 on Wayland", {"50"}) == [(1, "51")]
    assert unlisted_in("GNOME Shell 49, 50, and 51", {"50"}) == [(1, "49"), (1, "51")]
