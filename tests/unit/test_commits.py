# SPDX-License-Identifier: GPL-2.0-or-later
"""The commit message rules."""

import pytest

from tools.commits import problems

GOOD = (
    "feat(zoom): glide between zoom levels\n"
    "\n"
    "- ease each notch toward its level so a run of notches is one motion\n"
)


def test_a_message_that_follows_the_rules_passes() -> None:
    assert problems(GOOD) == []


def test_a_title_alone_passes() -> None:
    assert problems("fix(prefs): grey out the style when smoothing is off") == []


def test_git_comment_lines_are_ignored() -> None:
    assert problems(GOOD + "# Please enter the commit message\n") == []


@pytest.mark.parametrize(
    ("message", "problem"),
    [
        ("", "empty"),
        ("Add zoom", "type(scope): description"),
        ("feat(zoom): Glide", "type(scope): description"),
        ("feat(zoom): glide.", "ends with a period"),
        ("feat(zoom): " + "a" * 70, "over 72"),
        ("feat(zoom): glide\n- no blank line", "blank line"),
        ("feat(zoom): glide\n\nprose instead of a bullet", "neither"),
        ("feat(zoom): glide\n\n- " + "a" * 80, "over 72"),
        ("feat(zoom): glide\n\n- use `make check`", "markdown"),
        ("feat(zoom): glide\n\n- x\n\nCo-Authored-By: someone <a@b.c>", "co-authored-by"),
        ("feat(zoom): a seamless glide", "seamless"),
    ],
)
def test_a_message_that_breaks_a_rule_is_refused(message: str, problem: str) -> None:
    assert any(problem.lower() in found.lower() for found in problems(message)), problems(message)
