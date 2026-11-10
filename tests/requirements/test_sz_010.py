# SPDX-License-Identifier: GPL-2.0-or-later
"""SZ-010: zooming keeps the pointer where it is when GNOME's following pushes."""

import time
from dataclasses import dataclass

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from tests.requirements.conftest import Scene
from tests.shell import SCREEN, Json, Shell, number, step

scenarios("SZ-010-zooming-keeps-the-pointer-where-it-is-when-gnome-s-following-pushes.feature")

MAGNIFIER = "new imports.gi.Gio.Settings({schema_id: 'org.gnome.desktop.a11y.magnifier'})"
GNOME_FOLLOWING = {
    "pushes the view at its edges": "push",
    "moves the view with its contents": "proportional",
    "follows nothing": "none",
}
# The pointer's image in the test shell, across and down, at 1x. GNOME's push keeps the whole
# of it, grown by the zoom, in the view.
POINTER_IMAGE_PX = 24
SWIPE_STEP_PX = 10
POINTER_STEP_PX = 10
# About one frame at the test screen's 144 Hz, as a hand moves a mouse.
POINTER_STEP_MS = 7

Point = tuple[float, float]


@dataclass
class Drawn:
    """Where the pointer was drawn on the screen before the scenario's last zoom began, where
    the pointer itself was, where the view was before the pointer last moved, and where GNOME
    had the view's middle before zoom came on."""

    before: Point = (0.0, 0.0)
    pointer: Point = (0.0, 0.0)
    view_before: Point = (0.0, 0.0)
    middle_before: Point = (0.0, 0.0)


@pytest.fixture
def drawn() -> Drawn:
    return Drawn()


def point(value: Json) -> Point:
    assert isinstance(value, list)
    return number(value[0]), number(value[1])


def drawn_at(roi: Json, zoom: Json, pointer: Json, on: Json) -> Point:
    """Where the zoomed view draws the point the pointer is on: its place in the view times
    the zoom, or the pointer itself with zoom off."""
    x, y = point(pointer)
    if on is not True:
        return x, y
    left, top = point(roi)
    factor = number(zoom)
    return (x - left) * factor, (y - top) * factor


def kept_at(before: Point, pointer: Point, zoom: float) -> Point:
    """Where a pointer kept where it is is drawn at this zoom: where it was drawn, as near as
    keeps its whole image on the screen and the view within the screen."""
    kept: list[float] = []
    for axis in (0, 1):
        size = SCREEN[axis]
        place = min(max(before[axis], 0.0), size - POINTER_IMAGE_PX * zoom)
        start = min(max(pointer[axis] - place / zoom, 0.0), size - size / zoom)
        kept.append((pointer[axis] - start) * zoom)
    return kept[0], kept[1]


def proportional_middle(pointer: Point, zoom: float) -> Point:
    """Where GNOME's following that moves with the contents puts the view's middle: off the
    pointer by the pointer's place on the screen, as GNOME Shell 50's magnifier works it out,
    and within the screen."""
    padding = min(SCREEN) / 5 / zoom
    middle: list[float] = []
    for axis in (0, 1):
        size = SCREEN[axis]
        half = size / zoom / 2
        share = (pointer[axis] - size / 2) / (size / 2)
        middle.append(min(max(pointer[axis] - share * (half - padding), half), size - half))
    return middle[0], middle[1]


def state(shell: Shell) -> dict[str, Json]:
    value = shell.call(
        "const r = Main.magnifier.getZoomRegions()[0]; return {roi: r.getROI(), "
        "zoom: r.getMagFactor()[0], pointer: global.get_pointer(), on: Main.magnifier.isActive()};"
    )
    assert isinstance(value, dict)
    return value


def drawn_now(shell: Shell) -> Point:
    now = state(shell)
    return drawn_at(now["roi"], now["zoom"], now["pointer"], now["on"])


def record(shell: Shell) -> None:
    shell.call("return scrollZoomTest.record();")


def recorded(shell: Shell, scene: Scene) -> None:
    frames = shell.call("return scrollZoomTest.stopRecording();")
    assert isinstance(frames, list)
    scene.frames = [frame for frame in frames if isinstance(frame, dict)]


@given(parsers.parse("GNOME's own following {how}"))
def gnome_follows(shell: Shell, how: str) -> None:
    shell.call(f"{MAGNIFIER}.set_string('mouse-tracking', '{GNOME_FOLLOWING[how]}'); return true;")


@given(parsers.parse("the pointer is at {x:d}, {y:d}"))
def pointer_at(shell: Shell, drawn: Drawn, x: int, y: int) -> None:
    shell.run_steps([step(1, "moveTo", x, y)])
    shell.wait_until(f"scrollZoomTest.state().pointer.join() === '{x},{y}'")
    drawn.before = drawn_now(shell)
    drawn.pointer = (float(x), float(y))
    roi = state(shell)["roi"]
    assert isinstance(roi, list)
    left, top, width, height = (number(value) for value in roi)
    drawn.middle_before = (left + width / 2, top + height / 2)


@when(parsers.parse("the pointer moves {pixels:d} pixels left"))
def pointer_left(shell: Shell, scene: Scene, drawn: Drawn, pixels: int) -> None:
    now = state(shell)
    drawn.view_before = point(now["roi"])
    x, y = point(now["pointer"])
    record(shell)
    steps = [
        step(POINTER_STEP_MS, "moveTo", x - POINTER_STEP_PX * (i + 1), y)
        for i in range(pixels // POINTER_STEP_PX)
    ]
    shell.run_steps(steps)
    time.sleep(0.2)
    recorded(shell, scene)
    drawn.before = drawn_now(shell)
    drawn.pointer = point(state(shell)["pointer"])


@when(parsers.parse("Super is held and two fingers swipe {pixels:d} pixels {direction}"))
def swipe(shell: Shell, scene: Scene, pixels: int, direction: str) -> None:
    dy = -SWIPE_STEP_PX if direction == "up" else SWIPE_STEP_PX
    record(shell)
    steps: list[list[Json]] = [step(20, "press", "super")]
    steps += [step(15, "swipe", dy) for _ in range(pixels // SWIPE_STEP_PX)]
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


@then("GNOME's own following still pushes the view at its edges")
def still_pushes(shell: Shell) -> None:
    value = shell.call(f"return {MAGNIFIER}.get_string('mouse-tracking');")
    assert value == "push", f"GNOME's own following became {value}"


@then(
    parsers.parse(
        "the view stayed where it was on the screen as the pointer moved, "
        "within {tolerance:d} pixels"
    )
)
def view_stayed(shell: Shell, scene: Scene, drawn: Drawn, tolerance: int) -> None:
    bx, by = drawn.view_before
    moved = 0.0
    for frame in [*scene.frames, state(shell)]:
        x, y = point(frame["roi"])
        # As the screen shows it: a view moved one pixel of the unzoomed screen moves everything
        # on the screen by the zoom.
        moved = max(moved, max(abs(x - bx), abs(y - by)) * number(frame["zoom"]))
    assert moved <= tolerance, (
        f"the view moved {moved:.1f} pixels on the screen as the pointer moved, over "
        f"{len(scene.frames)} frames and where it rests at the end"
    )


@then(
    parsers.parse(
        "every frame kept the pointer where it was on the screen, within {tolerance:d} pixels"
    )
)
def pointer_kept(shell: Shell, scene: Scene, drawn: Drawn, tolerance: int) -> None:
    assert scene.frames, "no frame was drawn as zoom changed"
    frames = [*scene.frames, state(shell)]
    worst = 0.0
    for frame in frames:
        assert point(frame["pointer"]) == drawn.pointer, (
            f"the pointer itself moved, to {frame['pointer']}, from {drawn.pointer}"
        )
        x, y = drawn_at(frame["roi"], frame["zoom"], frame["pointer"], frame["on"])
        if frame["on"] is True:
            kx, ky = kept_at(drawn.before, drawn.pointer, number(frame["zoom"]))
        else:
            kx, ky = drawn.pointer
        worst = max(worst, abs(x - kx), abs(y - ky))
    bx, by = drawn.before
    assert worst <= tolerance, (
        f"the pointer was drawn {worst:.1f} pixels from where it was kept from {bx:.0f}, "
        f"{by:.0f}, over {len(scene.frames)} frames and where it rests at the end"
    )
    # The next zoom in the scenario starts from here.
    drawn.before = drawn_now(shell)


@then(
    parsers.parse(
        "every frame had the view where GNOME's moving with the contents puts it, "
        "within {tolerance:d} pixels"
    )
)
def proportional(shell: Shell, scene: Scene, drawn: Drawn, tolerance: int) -> None:
    frames = [frame for frame in [*scene.frames, state(shell)] if frame["on"] is True]
    assert frames, "no frame was drawn with zoom on"
    worst = 0.0
    for frame in frames:
        left, top = point(frame["roi"])
        factor = number(frame["zoom"])
        mx, my = proportional_middle(drawn.pointer, factor)
        middle = (left + SCREEN[0] / factor / 2, top + SCREEN[1] / factor / 2)
        worst = max(worst, abs(middle[0] - mx), abs(middle[1] - my))
    assert worst <= tolerance, (
        f"the view was {worst:.1f} pixels from where GNOME's moving with the contents puts it, "
        f"over {len(frames)} frames with zoom on"
    )


@then(
    parsers.parse(
        "every frame kept the view's middle where GNOME had it, within {tolerance:d} pixels"
    )
)
def middle_kept(shell: Shell, scene: Scene, drawn: Drawn, tolerance: int) -> None:
    frames = [frame for frame in [*scene.frames, state(shell)] if frame["on"] is True]
    assert frames, "no frame was drawn with zoom on"
    # GNOME keeps where it put the view's middle at the zoom before, so the middle moves only as
    # far as each zoom's view needs to stay within the screen.
    expected = list(drawn.middle_before)
    worst = 0.0
    for frame in frames:
        left, top = point(frame["roi"])
        factor = number(frame["zoom"])
        for axis, start in ((0, left), (1, top)):
            half = SCREEN[axis] / factor / 2
            expected[axis] = min(max(expected[axis], half), SCREEN[axis] - half)
            worst = max(worst, abs(start + half - expected[axis]))
    mx, my = drawn.middle_before
    assert worst <= tolerance, (
        f"the view's middle was {worst:.1f} pixels from where GNOME had it, {mx:.1f}, {my:.1f}, "
        f"over {len(frames)} frames with zoom on"
    )
