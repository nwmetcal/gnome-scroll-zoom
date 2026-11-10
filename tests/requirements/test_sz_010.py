# SPDX-License-Identifier: GPL-2.0-or-later
"""SZ-010: zooming keeps the pointer where it is when GNOME's following pushes."""

import time
from dataclasses import dataclass

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from tests.requirements.conftest import Scene
from tests.shell import Json, Shell, number, step

scenarios("SZ-010-zooming-keeps-the-pointer-where-it-is-when-gnome-pushes.feature")

MAGNIFIER = "new imports.gi.Gio.Settings({schema_id: 'org.gnome.desktop.a11y.magnifier'})"
SWIPE_STEP_PX = 10
POINTER_STEP_PX = 10
# About one frame at the test screen's 144 Hz, as a hand moves a mouse.
POINTER_STEP_MS = 7


@dataclass
class Drawn:
    """Where the pointer was drawn on the screen before the scenario's last zoom began."""

    before: tuple[float, float] = (0.0, 0.0)


@pytest.fixture
def drawn() -> Drawn:
    return Drawn()


def drawn_at(roi: Json, zoom: Json, pointer: Json, on: Json) -> tuple[float, float]:
    """Where the zoomed view draws the point the pointer is on: its place in the view times
    the zoom, or the pointer itself with zoom off."""
    assert isinstance(pointer, list)
    x, y = number(pointer[0]), number(pointer[1])
    if on is not True:
        return x, y
    assert isinstance(roi, list)
    factor = number(zoom)
    return (x - number(roi[0])) * factor, (y - number(roi[1])) * factor


def drawn_now(shell: Shell) -> tuple[float, float]:
    state = shell.call(
        "const r = Main.magnifier.getZoomRegions()[0]; return {roi: r.getROI(), "
        "zoom: r.getMagFactor()[0], pointer: global.get_pointer(), on: Main.magnifier.isActive()};"
    )
    assert isinstance(state, dict)
    return drawn_at(state["roi"], state["zoom"], state["pointer"], state["on"])


def record(shell: Shell) -> None:
    shell.call("return scrollZoomTest.record();")


def recorded(shell: Shell, scene: Scene) -> None:
    frames = shell.call("return scrollZoomTest.stopRecording();")
    assert isinstance(frames, list)
    scene.frames = [frame for frame in frames if isinstance(frame, dict)]


@given("GNOME's own following pushes the view at its edges")
def gnome_pushes(shell: Shell) -> None:
    shell.call(f"{MAGNIFIER}.set_string('mouse-tracking', 'push'); return true;")


@given(parsers.parse("the pointer is at {x:d}, {y:d}"))
def pointer_at(shell: Shell, drawn: Drawn, x: int, y: int) -> None:
    shell.run_steps([step(1, "moveTo", x, y)])
    shell.wait_until(f"scrollZoomTest.state().pointer.join() === '{x},{y}'")
    drawn.before = drawn_now(shell)


@when(parsers.parse("the pointer moves {pixels:d} pixels left"))
def pointer_left(shell: Shell, scene: Scene, drawn: Drawn, pixels: int) -> None:
    pointer = shell.state()["pointer"]
    assert isinstance(pointer, list)
    x, y = number(pointer[0]), number(pointer[1])
    record(shell)
    steps = [
        step(POINTER_STEP_MS, "moveTo", x - POINTER_STEP_PX * (i + 1), y)
        for i in range(pixels // POINTER_STEP_PX)
    ]
    shell.run_steps(steps)
    time.sleep(0.2)
    recorded(shell, scene)
    drawn.before = drawn_now(shell)


@when(parsers.parse("Super is held and two fingers swipe {pixels:d} pixels up"))
def swipe_up(shell: Shell, scene: Scene, pixels: int) -> None:
    record(shell)
    steps: list[list[Json]] = [step(20, "press", "super")]
    steps += [step(15, "swipe", -SWIPE_STEP_PX) for _ in range(pixels // SWIPE_STEP_PX)]
    steps += [step(15, "lift"), step(20, "release", "super")]
    shell.run_steps(steps)
    time.sleep(0.2)
    shell.settle(timeout_s=5)
    recorded(shell, scene)


@when("GNOME's zoom toggle turns zoom on")
def toggle_on(shell: Shell, scene: Scene) -> None:
    # GNOME's toggle, Super+Alt+8, sets this setting; the test shell runs no settings daemon.
    record(shell)
    shell.call(
        "new imports.gi.Gio.Settings({schema_id: 'org.gnome.desktop.a11y.applications'})"
        ".set_boolean('screen-magnifier-enabled', true); return true;"
    )
    shell.wait_until("scrollZoomTest.state().on")
    shell.settle()
    recorded(shell, scene)


@then("zoom is on")
def zoom_on(shell: Shell) -> None:
    assert shell.state()["on"] is True


@then(
    parsers.parse("the view stayed where it was as the pointer moved, within {tolerance:d} pixels")
)
def view_stayed(scene: Scene, tolerance: int) -> None:
    rois = [frame["roi"] for frame in scene.frames]
    assert rois, "no frame was drawn as the pointer moved"
    first = rois[0]
    assert isinstance(first, list)
    moved = 0.0
    for roi in rois:
        assert isinstance(roi, list)
        moved = max(moved, *(abs(number(roi[i]) - number(first[i])) for i in (0, 1)))
    assert moved <= tolerance, f"the view moved {moved:.1f} pixels as the pointer moved"


@then(
    parsers.parse(
        "every frame kept the pointer where it was on the screen, within {tolerance:d} pixels"
    )
)
def pointer_kept(shell: Shell, scene: Scene, drawn: Drawn, tolerance: int) -> None:
    assert scene.frames, "no frame was drawn as zoom changed"
    bx, by = drawn.before
    worst = 0.0
    for frame in scene.frames:
        x, y = drawn_at(frame["roi"], frame["zoom"], frame["pointer"], frame["on"])
        worst = max(worst, abs(x - bx), abs(y - by))
    end = drawn_now(shell)
    worst = max(worst, abs(end[0] - bx), abs(end[1] - by))
    assert worst <= tolerance, (
        f"the pointer was drawn {worst:.1f} pixels from {bx:.0f}, {by:.0f}, where it was before "
        f"the zoom, over {len(scene.frames)} frames and where it rests at the end"
    )
    # The next zoom in the scenario starts from here.
    drawn.before = end
