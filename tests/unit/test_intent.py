# SPDX-License-Identifier: GPL-2.0-or-later
"""A pull request's Intent section."""

from tests.paths import ROOT
from tools.intent import Intent, parsed, problems, touched

DONE = "Done when:\n\n- zoom glides\n"


def intent(requirements: str = "none", touches: str = "none") -> Intent:
    result = parsed(f"## Intent\n\nRequirements: {requirements}\nTouches: {touches}\n\n{DONE}")
    assert isinstance(result, Intent), result
    return result


def test_a_description_without_an_intent_is_refused() -> None:
    assert parsed("## Why\n\nBecause.\n") == "no ## Intent section"


def test_the_template_as_it_stands_is_refused() -> None:
    template = (ROOT / ".github" / "PULL_REQUEST_TEMPLATE.md").read_text()
    filled = template.replace("SZ-###, or none", "none")
    assert parsed(filled) == "no Done when: list"


def test_a_bad_id_is_refused() -> None:
    result = parsed(f"## Intent\n\nRequirements: SZ-1\nTouches: none\n\n{DONE}")
    assert isinstance(result, str) and "SZ-1" in result


def test_ids_and_done_when_lines_are_read() -> None:
    read = intent("SZ-001, SZ-004", "SZ-002")
    assert read.requirements == {"SZ-001", "SZ-004"}
    assert read.touches == {"SZ-002"}
    assert read.done_when == ("zoom glides",)


def test_a_feature_or_its_steps_touch_a_requirement() -> None:
    paths = [
        "requirements/SZ-003-the-view-follows.feature",
        "tests/requirements/test_sz_005.py",
        "scroll-zoom@nhicc/extension.js",
    ]
    assert touched(paths) == {"SZ-003", "SZ-005"}


def test_a_touched_requirement_must_be_declared() -> None:
    found = problems(intent("SZ-001"), ["tests/requirements/test_sz_002.py"])
    assert found == ["SZ-002: touched but declared under neither Requirements nor Touches"]


def test_a_declared_requirement_passes() -> None:
    assert problems(intent("SZ-001", "SZ-002"), ["tests/requirements/test_sz_002.py"]) == []
