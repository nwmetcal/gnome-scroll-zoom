# SPDX-License-Identifier: GPL-2.0-or-later
"""SZ-010: zooming keeps the pointer where it is when GNOME's following pushes."""

import time
from dataclasses import dataclass

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from tests.requirements.conftest import QUICK_GAP_MS, Scene
from tests.shell import SCREEN, Json, Shell, number, step

scenarios("SZ-010-zooming-keeps-the-pointer-where-it-is-when-gnome-s-following-pushes.feature")

MAGNIFIER = "new imports.gi.Gio.Settings({schema_id: 'org.gnome.desktop.a11y.magnifier'})"
GNOME_FOLLOWING = {
    "pushes the view at its edges": "push",
    "moves the view with its contents": "proportional",
    "follows nothing": "none",
}
# GNOME's zoomed view on half the screen, as its Screen Area setting names it, and where it
# lies: x, y, width, height.
VIEW_PORTS = {
    "top half": ("top-half", (0.0, 0.0, float(SCREEN[0]), SCREEN[1] / 2)),
    "left half": ("left-half", (0.0, 0.0, SCREEN[0] / 2, float(SCREEN[1]))),
    "bottom half": ("bottom-half", (0.0, SCREEN[1] / 2, float(SCREEN[0]), SCREEN[1] / 2)),
    "right half": ("right-half", (SCREEN[0] / 2, 0.0, SCREEN[0] / 2, float(SCREEN[1]))),
}
# The pointer's image in the test shell, across and down, at 1x. GNOME's push keeps the whole
# of it, grown by the zoom, in the view.
POINTER_IMAGE_PX = 24
SWIPE_STEP_PX = 10
POINTER_STEP_PX = 10
# About one frame at the test screen's 144 Hz, as a hand moves a mouse.
POINTER_STEP_MS = 7

Point = tuple[float, float]
Box = tuple[float, float, float, float]


@dataclass
class Drawn:
    """Where the pointer was drawn on the screen before the scenario's last zoom began, where
    the pointer itself was, where the view was before the pointer last moved, and where GNOME
    had the view's middle before zoom came on."""

    before: Point = (0.0, 0.0)
    pointer: Point = (0.0, 0.0)
    view_before: Point = (0.0, 0.0)
    middle_before: Point = (0.0, 0.0)
    view_port: Box = (0.0, 0.0, float(SCREEN[0]), float(SCREEN[1]))
    # Whether GNOME holds what its view shows within the screen; its Extend Outside Screen
    # Edges lets it go past.
    within_screen: bool = True


@pytest.fixture
def drawn() -> Drawn:
    return Drawn()


def point(value: Json) -> Point:
    assert isinstance(value, list)
    return number(value[0]), number(value[1])


def drawn_at(roi: Json, zoom: Json, pointer: Json, on: Json, view_port: Box) -> Point:
    """Where the zoomed view draws the point the pointer is on: from the view's own corner,
    its place in the view times the zoom, or the pointer itself with zoom off."""
    x, y = point(pointer)
    if on is not True:
        return x, y
    left, top = point(roi)
    factor = number(zoom)
    return view_port[0] + (x - left) * factor, view_port[1] + (y - top) * factor


def kept_at(
    before: Point, pointer: Point, zoom: float, view_port: Box, within_screen: bool = True
) -> Point:
    """Where a pointer kept where it is is drawn at this zoom: where it was drawn, as near as
    keeps its whole image in the view, and the part of the screen the view shows within the
    screen."""
    kept: list[float] = []
    for axis in (0, 1):
        origin, size = view_port[axis], view_port[axis + 2]
        place = min(max(before[axis], origin), origin + size - POINTER_IMAGE_PX * zoom)
        start = pointer[axis] - (place - origin) / zoom
        past = 0.0 if within_screen else max(pointer[axis] + POINTER_IMAGE_PX - SCREEN[axis], 0.0)
        start = min(max(start, 0.0), SCREEN[axis] - size / zoom + past)
        kept.append(origin + (pointer[axis] - start) * zoom)
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


def drawn_now(shell: Shell, view_port: Box) -> Point:
    now = state(shell)
    return drawn_at(now["roi"], now["zoom"], now["pointer"], now["on"], view_port)


def record(shell: Shell) -> None:
    shell.call("return scrollZoomTest.record();")


def recorded(shell: Shell, scene: Scene) -> None:
    frames = shell.call("return scrollZoomTest.stopRecording();")
    assert isinstance(frames, list)
    scene.frames = [frame for frame in frames if isinstance(frame, dict)]


@given(parsers.parse("GNOME's own following {how}"))
def gnome_follows(shell: Shell, how: str) -> None:
    shell.call(f"{MAGNIFIER}.set_string('mouse-tracking', '{GNOME_FOLLOWING[how]}'); return true;")


@given(parsers.parse("zoom was last on at {zoom:g}x around {x:d}, {y:d} and is off"))
def last_on_around(shell: Shell, zoom: float, x: int, y: int) -> None:
    # A view a person saw: GNOME's centred following puts its middle on the pointer, and
    # GNOME keeps that middle once zoom goes off.
    shell.call(f"{MAGNIFIER}.set_string('mouse-tracking', 'centered'); return true;")
    shell.run_steps([step(1, "moveTo", x, y)])
    shell.wait_until(f"scrollZoomTest.state().pointer.join() === '{x},{y}'")
    shell.call(f"return scrollZoomTest.zoomTo({zoom});")
    shell.wait_until("scrollZoomTest.state().on")
    shell.settle()
    shell.call(
        "new imports.gi.Gio.Settings({schema_id: 'org.gnome.desktop.a11y.applications'})"
        ".set_boolean('screen-magnifier-enabled', false); return true;"
    )
    shell.wait_until("!scrollZoomTest.state().on")


@given(parsers.parse("GNOME's zoomed view is on the {half} of the screen"))
def view_on_half(shell: Shell, drawn: Drawn, half: str) -> None:
    area, view_port = VIEW_PORTS[half]
    shell.call(f"{MAGNIFIER}.set_string('screen-position', '{area}'); return true;")
    drawn.view_port = view_port


@given("GNOME's zoomed view may go past the screen's edges")
def past_edges(shell: Shell, drawn: Drawn) -> None:
    shell.call(f"{MAGNIFIER}.set_boolean('scroll-at-edges', true); return true;")
    drawn.within_screen = False


@given(parsers.parse("the pointer is at {x:d}, {y:d}"))
def pointer_at(shell: Shell, drawn: Drawn, x: int, y: int) -> None:
    shell.run_steps([step(1, "moveTo", x, y)])
    shell.wait_until(f"scrollZoomTest.state().pointer.join() === '{x},{y}'")
    drawn.before = drawn_now(shell, drawn.view_port)
    drawn.pointer = (float(x), float(y))
    roi = state(shell)["roi"]
    assert isinstance(roi, list)
    left, top, width, height = (number(value) for value in roi)
    drawn.middle_before = (left + width / 2, top + height / 2)


@when(parsers.parse("the pointer moves {pixels:d} pixels left"))
def pointer_left(shell: Shell, scene: Scene, drawn: Drawn, pixels: int) -> None:
    move_pointer(shell, scene, drawn, -pixels)


@when(parsers.parse("the pointer moves {pixels:d} pixels right"))
def pointer_right(shell: Shell, scene: Scene, drawn: Drawn, pixels: int) -> None:
    move_pointer(shell, scene, drawn, pixels)


def move_pointer(shell: Shell, scene: Scene, drawn: Drawn, across_px: int) -> None:
    now = state(shell)
    drawn.view_before = point(now["roi"])
    x, y = point(now["pointer"])
    record(shell)
    way = 1 if across_px > 0 else -1
    steps = [
        step(POINTER_STEP_MS, "moveTo", x + way * POINTER_STEP_PX * (i + 1), y)
        for i in range(abs(across_px) // POINTER_STEP_PX)
    ]
    shell.run_steps(steps)
    time.sleep(0.2)
    recorded(shell, scene)
    drawn.before = drawn_now(shell, drawn.view_port)
    drawn.pointer = point(state(shell)["pointer"])


@when(
    parsers.parse(
        "Super is held and the wheel turns {up:d} notches up and then {down:d} down in one spin"
    )
)
def spin_and_back(shell: Shell, scene: Scene, up: int, down: int) -> None:
    record(shell)
    steps: list[list[Json]] = [step(20, "press", "super")]
    steps += [step(QUICK_GAP_MS, "notch", 1) for _ in range(up)]
    steps += [step(QUICK_GAP_MS, "notch", -1) for _ in range(down)]
    steps += [step(20, "release", "super")]
    shell.run_steps(steps, timeout_s=30)
    time.sleep(0.2)
    shell.settle()
    recorded(shell, scene)


@when(
    parsers.parse(
        "Super is held and the wheel turns {up:d} notches up, rests {rest_ms:d} ms, and turns "
        "{down:d} down"
    )
)
def spin_rest_and_back(shell: Shell, scene: Scene, up: int, rest_ms: int, down: int) -> None:
    record(shell)
    steps: list[list[Json]] = [step(20, "press", "super")]
    steps += [step(QUICK_GAP_MS, "notch", 1) for _ in range(up)]
    steps += [step(rest_ms if i == 0 else QUICK_GAP_MS, "notch", -1) for i in range(down)]
    steps += [step(20, "release", "super")]
    shell.run_steps(steps, timeout_s=30)
    time.sleep(0.2)
    shell.settle()
    recorded(shell, scene)


@when(
    parsers.parse(
        "Super is held and two fingers swipe {up:d} pixels up, then {back:d} back after resting "
        "{rest_ms:d} ms"
    )
)
def swipe_rest_and_back(shell: Shell, scene: Scene, up: int, rest_ms: int, back: int) -> None:
    record(shell)
    steps: list[list[Json]] = [step(20, "press", "super")]
    steps += [step(15, "swipe", -SWIPE_STEP_PX) for _ in range(up // SWIPE_STEP_PX)]
    steps += [
        step(rest_ms if i == 0 else 15, "swipe", SWIPE_STEP_PX)
        for i in range(back // SWIPE_STEP_PX)
    ]
    steps += [step(15, "lift"), step(20, "release", "super")]
    shell.run_steps(steps, timeout_s=30)
    time.sleep(0.2)
    shell.settle(timeout_s=10)
    recorded(shell, scene)


@when(
    parsers.parse(
        "Super is held and two fingers swipe {up:d} pixels up and {back:d} back without lifting"
    )
)
def swipe_and_back(shell: Shell, scene: Scene, up: int, back: int) -> None:
    record(shell)
    steps: list[list[Json]] = [step(20, "press", "super")]
    steps += [step(15, "swipe", -SWIPE_STEP_PX) for _ in range(up // SWIPE_STEP_PX)]
    steps += [step(15, "swipe", SWIPE_STEP_PX) for _ in range(back // SWIPE_STEP_PX)]
    steps += [step(15, "lift"), step(20, "release", "super")]
    shell.run_steps(steps, timeout_s=30)
    time.sleep(0.2)
    shell.settle(timeout_s=10)
    recorded(shell, scene)


@when(
    parsers.parse(
        "GNOME's zoom level is set to {zoom:g}x, and {delay_ms:d} ms later the wheel turns "
        "1 notch up with Super"
    )
)
def level_then_notch(shell: Shell, scene: Scene, zoom: float, delay_ms: int) -> None:
    # GNOME's keyboard zoom and its slider set this level; the test shell runs no settings
    # daemon. The mark, just before the notch, tells the frames drawn before the notch came
    # from those after it, as GNOME's glide moves the pointer until the notch takes hold.
    record(shell)
    shell.call(f"{MAGNIFIER}.set_double('mag-factor', {zoom}); return true;")
    steps = [step(delay_ms, "press", "super"), step(20, "mark"), step(1, "notch", 1)]
    shell.run_steps([*steps, step(20, "release", "super")])
    time.sleep(0.2)
    shell.settle()
    recorded(shell, scene)


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
        x, y = drawn_at(frame["roi"], frame["zoom"], frame["pointer"], frame["on"], drawn.view_port)
        if frame["on"] is True:
            kx, ky = kept_at(
                drawn.before,
                drawn.pointer,
                number(frame["zoom"]),
                drawn.view_port,
                drawn.within_screen,
            )
        else:
            kx, ky = drawn.pointer
        worst = max(worst, abs(x - kx), abs(y - ky))
    bx, by = drawn.before
    assert worst <= tolerance, (
        f"the pointer was drawn {worst:.1f} pixels from where it was kept from {bx:.0f}, "
        f"{by:.0f}, over {len(scene.frames)} frames and where it rests at the end"
    )


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


@then(
    parsers.parse(
        "every frame from the notch kept the pointer where it was drawn then, "
        "within {tolerance:d} pixels"
    )
)
def kept_from_notch(scene: Scene, drawn: Drawn, tolerance: int) -> None:
    marks = [i for i, frame in enumerate(scene.frames) if frame.get("mark") is True]
    assert marks, "no mark was recorded for the notch"
    before = [frame for frame in scene.frames[: marks[0]] if frame.get("on") is True]
    after = [frame for frame in scene.frames[marks[0] + 1 :] if frame.get("on") is True]
    assert before and after, "no frame was drawn before or after the notch"
    last = before[-1]
    bx, by = drawn_at(last["roi"], last["zoom"], last["pointer"], last["on"], drawn.view_port)
    worst = 0.0
    for frame in after:
        x, y = drawn_at(frame["roi"], frame["zoom"], frame["pointer"], frame["on"], drawn.view_port)
        worst = max(worst, abs(x - bx), abs(y - by))
    assert worst <= tolerance, (
        f"the pointer was drawn {worst:.1f} pixels from {bx:.0f}, {by:.0f}, where it was as the "
        f"notch came, over {len(after)} frames after it"
    )
