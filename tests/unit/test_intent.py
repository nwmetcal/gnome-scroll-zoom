# SPDX-License-Identifier: GPL-2.0-or-later
"""A pull request's Intent section, and the release tags its description names."""

import re

from tests.paths import ROOT
from tools.intent import Intent, parsed, problems, tag_problems, touched, version_name

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


def test_a_release_tag_named_in_a_command_must_be_version_name() -> None:
    body = "## Owner's steps\n\n```bash\ngit tag v1.0.0\ngit push origin v1.0.0\n```\n"
    assert tag_problems(body, "1.1.0") == [
        "names the tag v1.0.0, but version-name is 1.1.0: the release workflow takes only v1.1.0"
    ]


def test_a_tag_in_inline_code_is_held_too() -> None:
    assert tag_problems("Then run `gh release view v1.2.0`.", "1.1.0") != []


def test_the_tag_version_name_gives_passes() -> None:
    assert tag_problems("```\ngit tag v1.1.0 && git push origin v1.1.0\n```", "1.1.0") == []


def test_a_tag_in_a_list_item_s_fenced_block_is_held_too() -> None:
    body = "1. Tag it:\n\n   ```bash\n   git tag v1.0.0\n   ```\n2. Push it.\n"
    assert tag_problems(body, "1.1.0") != []


def test_a_tag_with_a_suffix_is_not_version_name_s() -> None:
    assert tag_problems("`git tag v1.1.0-rc1`", "1.1.0") != []


def test_a_version_in_prose_is_not_a_command() -> None:
    assert tag_problems("Since v1.0.0 zoom glides, and `make zip` builds it.", "1.1.0") == []


def test_the_extension_s_version_name_is_read() -> None:
    assert re.fullmatch(r"\d+\.\d+\.\d+", version_name())
