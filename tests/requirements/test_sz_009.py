# SPDX-License-Identifier: GPL-2.0-or-later
"""SZ-009: zoom follows keyboard focus and the text cursor only when asked."""

import time
from collections.abc import Generator
from dataclasses import dataclass

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from tests.paths import ROOT
from tests.requirements.conftest import Scene, zoom_to
from tests.shell import SCREEN, Json, Shell, number, step

scenarios("SZ-009-zoom-follows-keyboard-focus-and-the-text-cursor-only-when-asked.feature")

APP = ROOT / "tests" / "focus_app.js"
TITLE = "Focus test app"
UUID = "scroll-zoom@nhicc"
# What tests/focus_app.js draws, on the unzoomed screen, as boxes: x, y, width, height. The
# middle button's middle is a point; the line's text is its two characters' cells, as GNOME's
# accessibility places them in the test shell's monospace font, where the text cursor sits.
TARGETS = {
    "middle button's middle": (760.0, 400.0, 0.0, 0.0),
    "middle button whole": (700.0, 380.0, 120.0, 40.0),
    "line's text whole": (740.0, 560.0, 16.0, 16.0),
    "line's text": (740.0, 560.0, 16.0, 16.0),
}
SWITCHES = {"keyboard focus": "follow-focus", "the text cursor": "follow-text-cursor"}
MAGNIFIER = "new imports.gi.Gio.Settings({schema_id: 'org.gnome.desktop.a11y.magnifier'})"
FOLLOWING_KEYS = ("focus-tracking", "caret-tracking")
GNOME_FOLLOWING = {
    "centre the view on keyboard focus and on the text cursor": "centered",
    "push the view to keyboard focus and to the text cursor": "push",
    "follow keyboard focus and the text cursor in proportion": "proportional",
    "follow neither keyboard focus nor the text cursor": "none",
}
# A resting hand moves the pointer a little now and then; this keeps GNOME holding a follow
# back, since it waits for the pointer to rest 1000 ms.
WIGGLE_PX = 2
WIGGLE_GAP_MS = 50
# Long enough for a new GTK window to give its widget focus and show it to GNOME's
# accessibility, so the scenario's own Tab is the first focus change zoom sees.
APP_READY_S = 1.0


@dataclass
class Watch:
    """When the view started being watched, the scenario's last action, and where the pointer
    put the view when zoom came on."""

    since: float = 0.0
    start: tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)


@pytest.fixture
def watch() -> Watch:
    return Watch()


@pytest.fixture(autouse=True)
def app_and_extension(shell: Shell) -> Generator[None]:
    """The other requirements' test pattern sits above windows; it stays out of these. Each
    scenario leaves the extension on and no app open."""
    shell.call("return scrollZoomTest.hidePattern();")
    yield
    shell.call(f"Main.extensionManager.enableExtension('{UUID}'); return true;")
    shell.wait_until("scrollZoomTest.state().extension === 1")
    shell.call("return scrollZoomTest.closeWindows();")
    shell.wait_until("scrollZoomTest.windows().length === 0")
    shell.call("return scrollZoomTest.showPattern();")


def view(shell: Shell) -> tuple[float, float, float, float]:
    """The part of the screen GNOME's zoomed view shows: x, y, width, height."""
    roi = shell.call("return Main.magnifier.getZoomRegions()[0].getROI();")
    assert isinstance(roi, list) and len(roi) == 4
    x, y, width, height = (number(value) for value in roi)
    return x, y, width, height


def pointer_view(zoom: float, pointer: tuple[float, float]) -> tuple[float, float, float, float]:
    """Where the test shell's centred pointer following puts the view, as far as the screen's
    edges allow: x, y, width, height on the unzoomed screen."""
    sizes = (SCREEN[0] / zoom, SCREEN[1] / zoom)
    x, y = (
        min(max(pointer[axis] - sizes[axis] / 2, 0.0), SCREEN[axis] - sizes[axis])
        for axis in (0, 1)
    )
    return x, y, sizes[0], sizes[1]


def pointer_view_offset(roi: Json, zoom: Json, pointer: Json) -> float:
    """How far a view is from where the pointer puts it, in pixels of the unzoomed screen."""
    assert isinstance(roi, list) and isinstance(pointer, list)
    x, y, _, _ = (number(value) for value in roi)
    expected = pointer_view(number(zoom), (number(pointer[0]), number(pointer[1])))
    return max(abs(x - expected[0]), abs(y - expected[1]))


def set_gnome_following(shell: Shell, value: str) -> None:
    sets = " ".join(f"m.set_string('{key}', '{value}');" for key in FOLLOWING_KEYS)
    shell.call(f"const m = {MAGNIFIER}; {sets} return true;")


def open_app(shell: Shell, *args: str) -> None:
    shell.client("gjs", "-m", str(APP), *args)
    shell.wait_until(
        "global.get_window_actors().some(a => a.meta_window.get_title() === "
        f"'{TITLE}' && a.meta_window.is_fullscreen())",
        timeout_s=20,
    )
    shell.wait_until(f"global.display.focus_window?.get_title() === '{TITLE}'")
    time.sleep(APP_READY_S)


@given(parsers.parse("GNOME's own settings {how}"))
def gnome_follows(shell: Shell, how: str) -> None:
    set_gnome_following(shell, GNOME_FOLLOWING[how])


@given(parsers.parse("the maximum zoom is set to {zoom:g}x in Scroll Zoom's settings"))
def max_zoom(shell: Shell, zoom: float) -> None:
    shell.call(f"scrollZoomTest.settings().set_double('max-zoom', {zoom}); return true;")


def switch(shell: Shell, what: str) -> str:
    """The key of Scroll Zoom's switch for following `what`, which must exist."""
    key = SWITCHES[what]
    has = shell.call(f"return scrollZoomTest.settings().settings_schema.has_key('{key}');")
    assert has, f"Scroll Zoom has no setting for following {what}"
    return key


@given(parsers.parse("following {what} is turned {state} in Scroll Zoom's settings"))
def follow_switch(shell: Shell, what: str, state: str) -> None:
    value = {"on": "true", "off": "false"}[state]
    shell.call(
        f"scrollZoomTest.settings().set_boolean('{switch(shell, what)}', {value}); return true;"
    )


@given("the extension is turned off")
def given_off(shell: Shell) -> None:
    shell.call(f"Main.extensionManager.disableExtension('{UUID}'); return true;")
    shell.wait_until("scrollZoomTest.state().extension !== 1")


@given("the extension is turned on")
def given_on(shell: Shell) -> None:
    shell.call(f"Main.extensionManager.enableExtension('{UUID}'); return true;")
    shell.wait_until("scrollZoomTest.state().extension === 1")


TAB = [step(1, "press", "tab"), step(20, "release", "tab")]
SHIFT_TAB = [step(1, "press", "shift"), *TAB, step(20, "release", "shift")]


def wiggle_with(
    pointer: tuple[float, float], duration_ms: int, at_ms: dict[int, list[list[Json]]]
) -> list[list[Json]]:
    """A wiggle with other steps put in it, each set of them about `at` ms into it."""
    steps: list[list[Json]] = []
    for index, move in enumerate(wiggle(pointer, duration_ms)):
        for at, extra in at_ms.items():
            if at // WIGGLE_GAP_MS == index:
                steps += extra
        steps.append(move)
    return steps


def wiggle(pointer: tuple[float, float], duration_ms: int) -> list[list[Json]]:
    """Moves of the pointer 2 pixels back and forth every 50 ms, ending where it began."""
    x, y = pointer
    count = duration_ms // WIGGLE_GAP_MS
    return [
        step(WIGGLE_GAP_MS, "moveTo", x + (WIGGLE_PX if i % 2 == 0 else 0), y)
        for i in range(count - count % 2)
    ]


@given("the focus test app is open with its first button focused")
def app_open(shell: Shell) -> None:
    open_app(shell)


@given("the focus test app is open, moving the text cursor in its line on its own")
def app_printing(shell: Shell) -> None:
    open_app(shell, "--print")


@given(parsers.parse("zoom is on at {zoom:g}x with the pointer at {x:d}, {y:d}"))
def zoom_on_at_pointer(
    shell: Shell, scene: Scene, watch: Watch, zoom: float, x: int, y: int
) -> None:
    # Every frame from zoom on is watched: an app's own text cursor can pull the view away
    # as soon as zoom comes on.
    shell.call("return scrollZoomTest.record();")
    zoom_to(shell, scene, zoom, (float(x), float(y)))
    watch.since = time.monotonic()
    watch.start = pointer_view(zoom, (float(x), float(y)))


@when("Tab moves keyboard focus to the middle button")
def tab(shell: Shell, watch: Watch) -> None:
    shell.run_steps([step(1, "press", "tab"), step(20, "release", "tab")])
    watch.since = time.monotonic()


@when(parsers.parse("GNOME's own settings change to {how}"))
def gnome_changes(shell: Shell, watch: Watch, how: str) -> None:
    set_gnome_following(shell, GNOME_FOLLOWING[how])
    watch.since = time.monotonic()


@when("zoom goes off, Shift+Tab moves focus back to the first button, and zoom comes on again")
def zoom_off_and_back(shell: Shell, scene: Scene, watch: Watch) -> None:
    shell.call(
        "new imports.gi.Gio.Settings({schema_id: 'org.gnome.desktop.a11y.applications'})"
        ".set_boolean('screen-magnifier-enabled', false); return true;"
    )
    shell.wait_until("!scrollZoomTest.state().on")
    shell.run_steps(
        [step(20, "press", "shift"), step(20, "press", "tab")]
        + [step(20, "release", "tab"), step(20, "release", "shift")]
    )
    time.sleep(APP_READY_S)
    zoom_to(shell, scene, scene.zoom, scene.pointer)
    watch.since = time.monotonic()
    watch.start = pointer_view(scene.zoom, scene.pointer)


@when(
    parsers.parse("following {what} is on while the pointer moves for {duration_ms:d} ms, then off")
)
def follow_while_moving(
    shell: Shell, scene: Scene, watch: Watch, what: str, duration_ms: int
) -> None:
    key = switch(shell, what)
    moves = wiggle(scene.pointer, duration_ms)
    # The pointer is already moving as the switch comes on, so the first text cursor move it
    # sees is held, as the scenario says, and never shown at once.
    steps = [*moves[:2], step(1, "setBoolean", key, True), *moves[2:]]
    shell.run_steps([*steps, step(1, "setBoolean", key, False)], timeout_s=duration_ms / 1000 + 5)
    watch.since = time.monotonic()


@when(
    parsers.parse(
        "the extension is turned off as the pointer moves for {duration_ms:d} ms, "
        "and on as it stops"
    )
)
def off_while_moving(shell: Shell, scene: Scene, watch: Watch, duration_ms: int) -> None:
    moves = wiggle(scene.pointer, duration_ms)
    # The pointer is already moving as the extension goes off, so GNOME holds what it follows.
    steps = [*moves[:2], step(1, "disableExtension"), *moves[2:], step(1, "enableExtension")]
    shell.run_steps(steps, timeout_s=duration_ms / 1000 + 5)
    shell.wait_until("scrollZoomTest.state().extension === 1")
    watch.since = time.monotonic()


@when(
    parsers.parse(
        "Tab and then Shift+Tab move focus out and back as the pointer moves for {duration_ms:d} ms"
    )
)
def out_and_back(shell: Shell, scene: Scene, watch: Watch, duration_ms: int) -> None:
    steps = wiggle_with(scene.pointer, duration_ms, {200: TAB, 600: SHIFT_TAB})
    shell.run_steps(steps, timeout_s=duration_ms / 1000 + 5)
    watch.since = time.monotonic()


@when(
    parsers.parse(
        "Tab moves focus during a {duration_ms:d} ms pointer move, "
        "and the pointer then goes to {x:d}, {y:d}"
    )
)
def tab_then_go(shell: Shell, scene: Scene, watch: Watch, duration_ms: int, x: int, y: int) -> None:
    steps = wiggle_with(scene.pointer, duration_ms, {200: TAB})
    shell.run_steps([*steps, step(1, "moveTo", x, y)], timeout_s=duration_ms / 1000 + 5)
    watch.since = time.monotonic()


@when(
    parsers.parse(
        "Tab moves focus, and the extension is turned off, during a {duration_ms:d} ms pointer move"
    )
)
def tab_then_off(shell: Shell, scene: Scene, watch: Watch, duration_ms: int) -> None:
    off = [step(1, "disableExtension")]
    steps = wiggle_with(scene.pointer, duration_ms, {200: TAB, 600: off})
    shell.run_steps(steps, timeout_s=duration_ms / 1000 + 5)
    shell.wait_until("scrollZoomTest.state().extension !== 1")
    watch.since = time.monotonic()


@when("the extension is turned off")
def turn_off(shell: Shell, watch: Watch) -> None:
    shell.call(f"Main.extensionManager.disableExtension('{UUID}'); return true;")
    shell.wait_until("scrollZoomTest.state().extension !== 1")
    watch.since = time.monotonic()


def wait_out(watch: Watch, seconds: int) -> None:
    time.sleep(max(0.0, watch.since + seconds - time.monotonic()))


@then(
    parsers.parse(
        "for {seconds:d} s every frame has the view where the pointer puts it, "
        "within {tolerance:d} pixels"
    )
)
def stays_with_pointer(shell: Shell, watch: Watch, seconds: int, tolerance: int) -> None:
    wait_out(watch, seconds)
    frames = shell.call("return scrollZoomTest.stopRecording();")
    assert isinstance(frames, list)
    judged = [frame for frame in frames if isinstance(frame, dict) and frame["on"] is True]
    # A view that moves is redrawn, so a frame is drawn for any move; the last check is of
    # where the view rests, drawn or not.
    assert judged, "no frame was drawn with zoom on"
    offsets = [pointer_view_offset(f["roi"], f["zoom"], f["pointer"]) for f in judged]
    state = shell.call(
        "const r = Main.magnifier.getZoomRegions()[0]; "
        "return {roi: r.getROI(), zoom: r.getMagFactor()[0], pointer: global.get_pointer()};"
    )
    assert isinstance(state, dict)
    offsets.append(pointer_view_offset(state["roi"], state["zoom"], state["pointer"]))
    worst = max(offsets)
    assert worst <= tolerance, (
        f"the view was {worst:.1f} pixels from where the pointer puts it, over "
        f"{len(judged)} frames with zoom on and where it rests at the end"
    )


@then(parsers.parse("GNOME's own settings still {how}"))
def gnome_unchanged(shell: Shell, how: str) -> None:
    gets = ", ".join(f"m.get_string('{key}')" for key in FOLLOWING_KEYS)
    values = shell.call(f"const m = {MAGNIFIER}; return [{gets}];")
    wanted = [GNOME_FOLLOWING[how]] * len(FOLLOWING_KEYS)
    assert values == wanted, f"GNOME's own settings became {values}, not {wanted}"


@then(
    parsers.parse(
        "after {seconds:d} s the view shows the {target}, overshooting by at most {margin:d} pixels"
    )
)
def brought_into_view(shell: Shell, watch: Watch, seconds: int, target: str, margin: int) -> None:
    wait_out(watch, seconds)
    end = view(shell)
    box = TARGETS[target]
    for axis, name in ((0, "across"), (1, "down")):
        low, high = box[axis], box[axis] + box[axis + 2]
        start, size = watch.start[axis], watch.start[axis + 2]
        assert end[axis] <= low and high <= end[axis] + size, (
            f"the {target} is out of the view {name}: it covers {low:.0f} to {high:.0f}, "
            f"the view {end[axis]:.1f} to {end[axis] + size:.1f}"
        )
        # How far the view had to move to show the target, from where the pointer put it.
        needed = max(high - (start + size), start - low, 0.0)
        overshoot = abs(end[axis] - start) - needed
        assert overshoot <= margin, (
            f"the view moved {abs(end[axis] - start):.1f} pixels {name} where "
            f"{needed:.1f} show the {target}: an overshoot of {overshoot:.1f}"
        )


@then(
    parsers.parse(
        "after {seconds:d} s the view is centred on the {target}, within {tolerance:d} pixels"
    )
)
def centred_on_target(
    shell: Shell, watch: Watch, seconds: int, target: str, tolerance: int
) -> None:
    wait_out(watch, seconds)
    x, y, width, height = view(shell)
    left, top, box_width, box_height = TARGETS[target]
    middle = (left + box_width / 2, top + box_height / 2)
    off = max(abs(x + width / 2 - middle[0]), abs(y + height / 2 - middle[1]))
    assert off <= tolerance, f"the view's middle is {off:.1f} pixels from the {target}"


@then(
    parsers.parse(
        "for the next {seconds:d} s the view stays where it is, within {tolerance:d} pixels"
    )
)
def holds_still(shell: Shell, seconds: int, tolerance: int) -> None:
    x0, y0, _, _ = view(shell)
    shell.call("return scrollZoomTest.record();")
    time.sleep(seconds)
    frames = shell.call("return scrollZoomTest.stopRecording();")
    assert isinstance(frames, list)
    rois = [frame["roi"] for frame in frames if isinstance(frame, dict)]
    rois.append([*view(shell)])
    moved = 0.0
    for roi in rois:
        assert isinstance(roi, list)
        moved = max(moved, abs(number(roi[0]) - x0), abs(number(roi[1]) - y0))
    assert moved <= tolerance, (
        f"the view moved {moved:.1f} pixels over {len(rois) - 1} frames as the text cursor moved"
    )
