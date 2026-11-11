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


def test_a_release_command_is_read_wherever_it_stands() -> None:
    for body in (
        "Then run `gh release create v1.2.0 build/scroll-zoom.shell-extension.zip`.",
        "1. Tag it:\n\n   ```bash\n   git tag -a v1.0.0 -m Release\n   ```\n",
        "> [!IMPORTANT]\n> ```bash\n> git tag v1.0.0 && git push origin v1.0.0\n> ```\n",
        "```bash\ngit tag v1.0.0\n",
        "````\n```\ngit push origin refs/tags/v1.0.0\n```\n````\n",
        "then tag it with git tag v1.0.0 and push it.",
    ):
        assert tag_problems(body, "1.1.0") != [], body


def test_a_command_in_a_span_wrapped_across_lines_is_read_on() -> None:
    assert tag_problems("- tag it, `git tag\n  v1.0.0`, then push", "1.1.0") != []
    assert tag_problems("`git tag v1.1.0 && git push origin\n  v1.0.0`", "1.1.0") != []
    assert tag_problems("> `git push origin main\n> v1.0.0`", "1.1.0") != []
    assert tag_problems("``git tag\nv1.0.0``", "1.1.0") != []


def test_a_command_outside_a_span_ends_with_its_line() -> None:
    assert tag_problems("Use git tag to mark it.\nSince v1.0.0 it glides.", "1.1.0") == []
    assert tag_problems("```\ngit tag v1.1.0\nv1.0.0 was last\n```", "1.1.0") == []
    assert tag_problems("`git push origin\n\nv1.0.0` is a new paragraph", "1.1.0") == []


def test_a_tag_with_any_suffix_is_not_version_name_s() -> None:
    for tag in ("v1.1.0-rc1", "v1.1.0+1", "v1.1.0_rc1", "v1.1.0.1"):
        assert tag_problems(f"`git tag {tag}`", "1.1.0") == [
            f"names the tag {tag}, but version-name is 1.1.0: "
            "the release workflow takes only v1.1.0"
        ]


def test_the_tag_version_name_gives_passes() -> None:
    body = "```\ngit tag -a v1.1.0 -m 'Scroll Zoom v1.1.0' && git push origin v1.1.0\n```"
    assert tag_problems(body, "1.1.0") == []
    assert tag_problems("`git tag v1.1.0`, then `make zip`.", "1.1.0") == []


def test_a_tag_named_through_a_variable_passes() -> None:
    assert tag_problems('```\ngit tag "v$version" origin/main\n```', "1.1.0") == []


def test_an_older_version_outside_a_release_command_passes() -> None:
    for body in (
        "Since v1.0.0 zoom glides, and `make zip` builds it.",
        "`git log --oneline v1.0.0..origin/main`",
        "```yaml\n- uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1\n```",
        "```\nthe tag v1.0.0 does not match version-name 1.1.0\n```",
        "`git tag v1.1.0\n  `, while v1.0.0 stays as it was, and `make zip`",
    ):
        assert tag_problems(body, "1.1.0") == [], body


def test_a_command_that_deletes_lists_or_verifies_a_tag_passes() -> None:
    for command in (
        "git tag -d v1.0.0-rc1",
        "git push --delete origin v1.0.0-rc1",
        "git push origin :refs/tags/v1.0.0-rc1",
        "git tag --list v1.0.0",
        "git tag -v v1.0.0",
    ):
        assert tag_problems(f"`{command}`", "1.1.0") == [], command


def test_the_extension_s_version_name_is_read() -> None:
    assert re.fullmatch(r"\d+\.\d+\.\d+", version_name())
