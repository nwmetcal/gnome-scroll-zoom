# SPDX-License-Identifier: GPL-2.0-or-later
"""SZ-001: holding Super and scrolling zooms the screen."""

import time

from pytest_bdd import parsers, scenarios, then, when

from tests.requirements.conftest import held
from tests.shell import Json, Shell, number, step

scenarios("SZ-001-holding-super-and-scrolling-zooms-the-screen.feature")

SWIPE_STEP_PX = 10


@when(parsers.parse("{keys} is held and two fingers swipe {pixels:d} pixels up"))
def swipe_up(shell: Shell, keys: str, pixels: int) -> None:
    steps: list[list[Json]] = [step(20, "press", key) for key in held(keys)]
    steps += [step(15, "swipe", -SWIPE_STEP_PX) for _ in range(pixels // SWIPE_STEP_PX)]
    steps += [step(15, "lift")]
    steps += [step(20, "release", key) for key in reversed(held(keys))]
    shell.run_steps(steps)
    time.sleep(0.2)
    shell.settle(timeout_s=5)


@then("the Activities overview is closed")
def overview_closed(shell: Shell) -> None:
    assert shell.state()["overview"] is False


@then(parsers.parse("GNOME's zoom toggle turns zoom on at {zoom:g}x"))
def toggle_on(shell: Shell, zoom: float) -> None:
    # GNOME's toggle, Super+Alt+8, sets this setting; the test shell runs no settings daemon.
    shell.call(
        "new imports.gi.Gio.Settings({schema_id: 'org.gnome.desktop.a11y.applications'})"
        ".set_boolean('screen-magnifier-enabled', true); return true;"
    )
    shell.wait_until("scrollZoomTest.state().on")
    shell.settle()
    state = shell.state()
    assert abs(number(state["zoom"]) / zoom - 1) < 0.005, state
