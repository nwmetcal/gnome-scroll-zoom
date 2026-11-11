# SPDX-License-Identifier: GPL-2.0-or-later
"""Each requirement is a feature named by its id and title, titled by its id, with its steps."""

import re

from tests.paths import REQUIREMENTS, ROOT

FILE = re.compile(r"^(SZ-\d{3})-[a-z0-9-]+\.feature$")
TITLE = re.compile(r"^Feature: (SZ-\d{3}) \S")
WORD = re.compile(r"[a-z0-9]+")
TAGS = re.compile(r"^@\S+(?: @\S+)*$")
STEPS = ROOT / "tests" / "requirements"


def features() -> list[tuple[str, str]]:
    return [(path.name, path.read_text()) for path in sorted(REQUIREMENTS.glob("*.feature"))]


def test_there_are_requirements() -> None:
    assert features()


def test_each_feature_is_named_and_titled_by_its_id() -> None:
    for name, text in features():
        named = FILE.match(name)
        assert named, f"{name}: name it SZ-###-its-title.feature"
        titles = [TITLE.match(line) for line in text.splitlines() if line.startswith("Feature:")]
        assert len(titles) == 1 and titles[0], f"{name}: title it 'Feature: SZ-### ...'"
        assert titles[0].group(1) == named.group(1), (
            f"{name}: the title's id differs from the name's"
        )


def named_for(title: str) -> str:
    """The file a feature titled 'SZ-### Its title' is named: its id, then its title's words,
    lowercased and joined by hyphens, as 'GNOME's' becomes 'gnome-s'."""
    rid, words = title.removeprefix("Feature: ").split(" ", 1)
    return "-".join([rid, *WORD.findall(words.lower())]) + ".feature"


def test_a_feature_is_named_for_its_title_s_words() -> None:
    assert named_for("Feature: SZ-007 GNOME's keyboard zoom glides too") == (
        "SZ-007-gnome-s-keyboard-zoom-glides-too.feature"
    )
    assert (
        named_for("Feature: SZ-900 Zoom, at 2.5x, glides") == "SZ-900-zoom-at-2-5x-glides.feature"
    )


def test_each_feature_is_named_for_its_title() -> None:
    for name, text in features():
        titles = [line for line in text.splitlines() if line.startswith("Feature:")]
        assert len(titles) == 1, f"{name}: give it one 'Feature: SZ-### ...' title"
        assert name == named_for(titles[0]), f"{name}: name it {named_for(titles[0])}"


def test_no_two_features_share_an_id() -> None:
    ids = [match.group(1) for name, _ in features() if (match := FILE.match(name))]
    assert len(ids) == len(set(ids)), sorted(ids)


def test_each_feature_starts_with_its_tags() -> None:
    for name, text in features():
        first = text.splitlines()[0]
        assert TAGS.match(first), f"{name}: the first line holds its tags"


def test_each_feature_has_a_steps_module_named_for_its_id_that_loads_it() -> None:
    for name, _ in features():
        number = name[3:6]
        module = STEPS / f"test_sz_{number}.py"
        assert module.exists(), f"{name}: its steps go in {module.relative_to(ROOT)}"
        assert f'scenarios("{name}")' in module.read_text(), f"{module.name} must load {name}"


def test_each_steps_module_has_a_feature() -> None:
    numbers = {name[3:6] for name, _ in features()}
    for module in STEPS.glob("test_sz_*.py"):
        assert module.stem.removeprefix("test_sz_") in numbers, f"{module.name} has no feature"
