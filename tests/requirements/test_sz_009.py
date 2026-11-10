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
# The middles of what tests/focus_app.js draws, on the unzoomed screen.
MIDDLES = {"middle button": (760.0, 400.0), "line": (760.0, 572.0)}
SWITCHES = {"keyboard focus": "follow-focus", "the text cursor": "follow-text-cursor"}
MAGNIFIER = "new imports.gi.Gio.Settings({schema_id: 'org.gnome.desktop.a11y.magnifier'})"
FOLLOWING_KEYS = ("focus-tracking", "caret-tracking")
# Long enough for a new GTK window to give its widget focus and show it to GNOME's
# accessibility, so the scenario's own Tab is the first focus change zoom sees.
APP_READY_S = 1.0


@dataclass
class Watch:
    """When the view started being watched: the scenario's last action."""

    since: float = 0.0


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


def pointer_view_offset(roi: Json, zoom: Json, pointer: Json) -> float:
    """How far a view's middle is from where the test shell's centred pointer following puts
    it, as far as the screen's edges allow, in pixels of the unzoomed screen."""
    assert isinstance(roi, list) and isinstance(pointer, list)
    x, y, width, height = (number(value) for value in roi)
    factor = number(zoom)
    worst = 0.0
    for axis, (start, size) in enumerate(((x, width), (y, height))):
        screen = SCREEN[axis]
        half = screen / factor / 2
        expected = min(max(number(pointer[axis]), half), screen - half)
        worst = max(worst, abs(start + size / 2 - expected))
    return worst


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


@given("GNOME's own settings centre the view on keyboard focus and on the text cursor")
def gnome_centres(shell: Shell) -> None:
    set_gnome_following(shell, "centered")


@given(parsers.parse("following {what} is turned on in Scroll Zoom's settings"))
def follow_on(shell: Shell, what: str) -> None:
    key = SWITCHES[what]
    has = shell.call(f"return scrollZoomTest.settings().settings_schema.has_key('{key}');")
    assert has, f"Scroll Zoom has no setting for following {what}"
    shell.call(f"scrollZoomTest.settings().set_boolean('{key}', true); return true;")


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


@when("Tab moves keyboard focus to the middle button")
def tab(shell: Shell, watch: Watch) -> None:
    shell.run_steps([step(1, "press", "tab"), step(20, "release", "tab")])
    watch.since = time.monotonic()


@when("GNOME's own settings change to centre the view on keyboard focus and on the text cursor")
def gnome_changes(shell: Shell, watch: Watch) -> None:
    set_gnome_following(shell, "centered")
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


@then("GNOME's own settings still centre the view on keyboard focus and on the text cursor")
def gnome_unchanged(shell: Shell) -> None:
    gets = ", ".join(f"m.get_string('{key}')" for key in FOLLOWING_KEYS)
    values = shell.call(f"const m = {MAGNIFIER}; return [{gets}];")
    assert values == ["centered", "centered"], f"GNOME's own settings became {values}"


@then(
    parsers.parse(
        "after {seconds:d} s the view shows the {target}'s middle, within {margin:d} pixels "
        "of its edge"
    )
)
def brought_into_view(shell: Shell, watch: Watch, seconds: int, target: str, margin: int) -> None:
    wait_out(watch, seconds)
    x, y, width, height = view(shell)
    tx, ty = MIDDLES[target]
    inside = x <= tx <= x + width and y <= ty <= y + height
    edge = min(tx - x, x + width - tx, ty - y, y + height - ty)
    assert inside, f"the {target}'s middle is out of the view, which shows {x:.0f}, {y:.0f}"
    assert edge <= margin, f"the {target}'s middle is {edge:.0f} pixels from the view's edge"


@then(
    parsers.parse(
        "after {seconds:d} s the view is centred on the {target}'s middle, "
        "within {tolerance:d} pixels"
    )
)
def centred_on_target(
    shell: Shell, watch: Watch, seconds: int, target: str, tolerance: int
) -> None:
    wait_out(watch, seconds)
    x, y, width, height = view(shell)
    tx, ty = MIDDLES[target]
    off = max(abs(x + width / 2 - tx), abs(y + height / 2 - ty))
    assert off <= tolerance, f"the view's middle is {off:.1f} pixels from the {target}'s middle"
