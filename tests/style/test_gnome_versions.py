# SPDX-License-Identifier: GPL-2.0-or-later
"""Every GNOME major a page or a tool names is one metadata.json lists, so a change to
shell-version finds each place to update (decision 0008). Decisions keep their history."""

import json
import re
from typing import cast

from tests.paths import EXTENSION, ROOT
from tests.style.test_words import tracked

METADATA: dict[str, object] = json.loads((EXTENSION / "metadata.json").read_text())
NAMED = re.compile(r"\bGNOME(?: Shell)? (\d{2,3})\b")


def unlisted(listed: set[str]) -> list[str]:
    """Each line outside docs/decisions/ that names a GNOME major not among listed."""
    found: list[str] = []
    for path in tracked():
        if path.startswith("docs/decisions/"):
            continue
        for number, line in enumerate((ROOT / path).read_text().splitlines(), start=1):
            found += [
                f"{path}:{number}: GNOME {major}"
                for major in NAMED.findall(line)
                if major not in listed
            ]
    return found


def test_each_gnome_major_named_is_one_metadata_lists() -> None:
    listed = {str(major) for major in cast("list[object]", METADATA["shell-version"])}
    found = unlisted(listed)
    assert not found, "name a major metadata.json lists:\n" + "\n".join(found)


def test_the_check_finds_a_major_no_longer_listed() -> None:
    assert unlisted(set()), "the README names the GNOME it needs"
