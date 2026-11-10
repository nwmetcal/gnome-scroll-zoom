# SPDX-License-Identifier: GPL-2.0-or-later
"""SZ-001: holding Super and scrolling zooms the screen."""

import time

from pytest_bdd import given, parsers, scenarios, then, when

from tests.requirements.conftest import Scene, held
from tests.shell import SCREEN, Json, Shell, number, step

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


@given(parsers.parse("the pointer is at {x:d}, {y:d}"))
def pointer_at(shell: Shell, x: int, y: int) -> None:
    shell.run_steps([step(1, "moveTo", x, y)])
    shell.wait_until(f"scrollZoomTest.state().pointer.join() === '{x},{y}'")


@then("zoom is on")
def zoom_on(shell: Shell) -> None:
    assert shell.state()["on"] is True


@then(parsers.parse("the zoomed view is centred on the pointer, within {tolerance:d} pixels"))
def centred_on_pointer(shell: Shell, tolerance: int) -> None:
    # The test shell's tracking is GNOME's "centered": the view's middle is the pointer.
    view = shell.call(
        "const [x, y, w, h] = Main.magnifier.getZoomRegions()[0].getROI();"
        " return [x + w / 2, y + h / 2];"
    )
    pointer = shell.state()["pointer"]
    assert isinstance(view, list) and isinstance(pointer, list)
    off = max(abs(number(view[i]) - number(pointer[i])) for i in range(2))
    assert off <= tolerance, f"the view is centred on {view}, the pointer is at {pointer}"


@then(
    parsers.parse(
        "on every frame of the spin the view was where centred tracking puts it,"
        " within {tolerance:d} pixels"
    )
)
def followed_every_frame(scene: Scene, tolerance: int) -> None:
    # Centred tracking puts the view's middle on the pointer, moved in from the screen's
    # edges as far as the view's own size needs.
    width, height = SCREEN
    worst = 0.0
    judged = 0
    for frame in scene.frames:
        if frame["on"] is not True:
            continue
        roi, pointer = frame["roi"], frame["pointer"]
        assert isinstance(roi, list) and isinstance(pointer, list)
        x, y, w, h = (number(v) for v in roi)
        want_x = min(max(number(pointer[0]), w / 2), width - w / 2)
        want_y = min(max(number(pointer[1]), h / 2), height - h / 2)
        worst = max(worst, abs(x + w / 2 - want_x), abs(y + h / 2 - want_y))
        judged += 1
    assert judged > 10, f"only {judged} frames were drawn with zoom on"
    assert worst <= tolerance, f"a frame of the spin had the view {worst:.1f} pixels off"


@then("the Activities overview is closed")
def overview_closed(shell: Shell) -> None:
    assert shell.state()["overview"] is False


def toggle(shell: Shell) -> None:
    # GNOME's toggle, Super+Alt+8, sets this setting; the test shell runs no settings daemon.
    shell.call(
        "new imports.gi.Gio.Settings({schema_id: 'org.gnome.desktop.a11y.applications'})"
        ".set_boolean('screen-magnifier-enabled', true); return true;"
    )
    shell.wait_until("scrollZoomTest.state().on")
    shell.settle()


@when("GNOME's zoom toggle turns zoom on")
def toggle_on_now(shell: Shell) -> None:
    toggle(shell)


@then(parsers.parse("GNOME's zoom toggle turns zoom on at {zoom:g}x"))
def toggle_on(shell: Shell, zoom: float) -> None:
    toggle(shell)
    state = shell.state()
    assert abs(number(state["zoom"]) / zoom - 1) < 0.005, state
