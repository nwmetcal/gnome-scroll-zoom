# SPDX-License-Identifier: GPL-2.0-or-later
"""Each requirement is a feature named and titled by its id, with its steps beside it."""

import re

from tests.paths import REQUIREMENTS, ROOT

FILE = re.compile(r"^(SZ-\d{3})-[a-z0-9-]+\.feature$")
TITLE = re.compile(r"^Feature: (SZ-\d{3}) \S")
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
