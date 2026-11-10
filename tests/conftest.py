# SPDX-License-Identifier: GPL-2.0-or-later
"""Requirements as code: ids, kinds, where a scenario can run, and the traceability matrix."""

import re
from collections.abc import Callable, Generator
from dataclasses import dataclass

import pytest
from pytest_bdd.scenario import scenario_wrapper_template_registry
from pytest_bdd.utils import registry_get_safe

from tests.paths import BUILD, ROOT
from tests.shell import Shell, gnome_shell_50, new_root

ID = re.compile(r"^(SZ-\d{3}) \S")
KINDS = {"invariant", "golden"}
SHELL = "shell"
SCENARIO_TESTS = ROOT / "tests" / "requirements"


@dataclass
class Row:
    requirement: str
    scenario: str
    kind: str
    shell: bool
    test: str
    status: str = "not run"


ROWS = pytest.StashKey[dict[str, Row]]()


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--shell",
        action="store_true",
        help="also run the scenarios tagged @shell, in a private headless GNOME Shell 50",
    )


def pytest_bdd_apply_tag(tag: str, function: Callable[..., object]) -> bool | None:
    if tag in KINDS | {SHELL}:
        getattr(pytest.mark, tag)(function)
        return True
    raise pytest.UsageError(f"@{tag} is not a tag a requirement may carry")


def _row(item: pytest.Item, feature_name: str, scenario_name: str) -> Row:
    match = ID.match(feature_name)
    if match is None:
        raise pytest.UsageError(f"{feature_name}: the feature title must start with its SZ-### id")
    kinds = [kind for kind in sorted(KINDS) if item.get_closest_marker(kind)]
    if len(kinds) != 1:
        raise pytest.UsageError(f"{feature_name}: tag exactly one of @invariant, @golden")
    shell = item.get_closest_marker(SHELL) is not None
    callspec = getattr(item, "callspec", None)
    if callspec is not None:
        # An outline's examples share its name; the matrix says which one each row is.
        scenario_name = f"{scenario_name} [{callspec.id}]"
    return Row(match.group(1), scenario_name, kinds[0], shell, item.nodeid)


def pytest_collection_modifyitems(
    session: pytest.Session, config: pytest.Config, items: list[pytest.Item]
) -> None:
    rows: dict[str, Row] = {}
    shell_wanted = bool(config.getoption("--shell"))
    for item in items:
        # pytest-bdd keeps no public way to reach a test's scenario; this registry is internal.
        scenario = registry_get_safe(scenario_wrapper_template_registry, getattr(item, "obj", None))
        if scenario is None:
            if item.path.is_relative_to(SCENARIO_TESTS):
                raise pytest.UsageError(f"{item.nodeid}: no scenario found; did pytest-bdd change?")
            continue
        row = _row(item, scenario.feature.name, scenario.name)
        if row.shell and not shell_wanted:
            item.add_marker(pytest.mark.skip(reason="pending: it needs the test shell (--shell)"))
        rows[item.nodeid] = row
    session.config.stash[ROWS] = rows


@pytest.hookimpl(wrapper=True)
def pytest_runtest_makereport(
    item: pytest.Item, call: pytest.CallInfo[None]
) -> Generator[None, pytest.TestReport, pytest.TestReport]:
    report = yield
    row = item.config.stash.get(ROWS, dict[str, Row]()).get(item.nodeid)
    if row is not None:
        if report.skipped:
            row.status = "pending"
        elif report.failed:
            row.status = "failed"
        elif call.when == "call":
            row.status = "passed"
    return report


def pytest_sessionfinish(session: pytest.Session) -> None:
    rows = session.config.stash.get(ROWS, dict[str, Row]())
    if not rows:
        return
    BUILD.mkdir(exist_ok=True)
    lines = [
        "# Traceability",
        "",
        "| Requirement | Scenario | Kind | Needs the shell | Status |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in sorted(rows.values(), key=lambda r: (r.requirement, r.test)):
        shell = "yes" if row.shell else "no"
        lines.append(
            f"| {row.requirement} | {row.scenario} | {row.kind} | {shell} | {row.status} |"
        )
    (BUILD / "traceability.md").write_text("\n".join(lines) + "\n")


@pytest.fixture(scope="session")
def test_shell() -> Generator[Shell]:
    """One private test shell for the whole run."""
    if not gnome_shell_50():
        pytest.fail("the @shell scenarios need GNOME Shell 50 on this machine")
    shell = Shell(new_root())
    shell.start()
    yield shell
    shell.stop()


@pytest.fixture
def shell(test_shell: Shell) -> Shell:
    """The test shell, reset to zoom off and the extension's defaults."""
    test_shell.call("return scrollZoomTest.reset();")
    test_shell.wait_until("!scrollZoomTest.state().on")
    test_shell.settle()
    return test_shell
