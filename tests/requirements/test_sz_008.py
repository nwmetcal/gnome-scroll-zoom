# SPDX-License-Identifier: GPL-2.0-or-later
"""SZ-008: zoom works over full-screen apps."""

import time
from collections.abc import Generator

import numpy as np
import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from tests.images import Box, crop, in_between_fraction, luma, zoomed
from tests.paths import ROOT
from tests.requirements.conftest import REPAINT_S, Scene, capture, set_style, zoom_to
from tests.shell import SCREEN, Shell, number, step

scenarios("SZ-008-zoom-works-over-full-screen-apps.feature")

APP = ROOT / "tests" / "full_screen_app.js"
TITLE = "Full-screen test app"
# Where tests/full_screen_app.js draws, on the unzoomed screen.
TEXT = Box(120, 120, 480, 100)
BAR_Y = 620.0
BAR_LEFT, BAR_TRAVEL = 500.0, 280.0
# Above the bar, so the zoomed pointer, drawn down and right from it, stays off the row the
# bar is measured on.
BAR_VIEW = (BAR_LEFT + BAR_TRAVEL / 2, BAR_Y - 80)
# Where the pointer rests to zoom on the text: clear of the screen's edges, so the view is
# centred on it at 2x, and off the text, so the zoomed pointer hides none of it.
TEXT_VIEW = (400.0, 260.0)


@pytest.fixture(autouse=True)
def no_pattern(shell: Shell) -> Generator[None]:
    """The other requirements' test pattern sits above windows; it stays out of these."""
    shell.call("return scrollZoomTest.hidePattern();")
    yield
    shell.call("return scrollZoomTest.closeWindows();")
    shell.wait_until("scrollZoomTest.windows().length === 0")
    shell.call("return scrollZoomTest.showPattern();")


def open_app(shell: Shell, kind: str, *args: str) -> None:
    command = ["gjs", "-m", str(APP), *args]
    if kind == "X11":
        x = shell.call("return scrollZoomTest.xDisplay();")
        assert isinstance(x, dict) and x["display"], f"the test shell has no X display: {x}"
        command = [
            "env",
            "GDK_BACKEND=x11",
            f"DISPLAY={x['display']}",
            f"XAUTHORITY={x['authority']}",
            *command,
        ]
    shell.client(*command)
    shell.wait_until(f"scrollZoomTest.windows().includes('{TITLE}')", timeout_s=20)
    shell.wait_until(
        "global.get_window_actors().some(a => a.meta_window.get_title() === "
        f"'{TITLE}' && a.meta_window.is_fullscreen())",
        timeout_s=10,
    )
    x, y = TEXT_VIEW
    shell.run_steps([step(1, "moveTo", x, y)])
    shell.wait_until(f"scrollZoomTest.state().pointer.join() === '{int(x)},{int(y)}'")
    wait_for_text(shell)


def wait_for_text(shell: Shell, timeout_s: float = 10.0) -> None:
    """Wait until the app's text is on screen: an X11 app draws its first frame later."""
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if float(crop(luma(shell.screenshot("app-ready")), TEXT).min()) < 0.5:
            time.sleep(REPAINT_S)
            return
        time.sleep(0.2)
    raise AssertionError("the app's text never appeared on screen")


@given(parsers.parse("a full-screen {kind} app"))
def full_screen_app(shell: Shell, kind: str) -> None:
    open_app(shell, kind)


@given(
    "a full-screen Wayland app that the person has allowed to take over the keyboard's shortcuts"
)
def app_with_shortcuts(shell: Shell) -> None:
    open_app(shell, "Wayland", "--take-shortcuts")
    # GNOME asks the person; Enter chooses Allow, the dialog's default.
    time.sleep(1.0)
    shell.run_steps([step(20, "press", "return"), step(20, "release", "return")])
    time.sleep(0.5)
    # Taken over, Super alone no longer opens the Activities overview.
    shell.run_steps([step(20, "press", "super"), step(60, "release", "super")])
    time.sleep(0.5)
    assert shell.state()["overview"] is False, "the app did not take over the keyboard's shortcuts"


@given(parsers.parse("zoom is on at {zoom:g}x over the app's moving bar"))
def zoom_on_bar(shell: Shell, scene: Scene, zoom: float) -> None:
    zoom_to(shell, scene, zoom, BAR_VIEW)


@then(
    "the app's zoomed text has at most two thirds as many in-between pixels as with GNOME's scaling"
)
def app_text_sharp(shell: Shell, scene: Scene) -> None:
    state = shell.state()
    pointer = state["pointer"]
    assert isinstance(pointer, list)
    box = zoomed(TEXT, (number(pointer[0]), number(pointer[1])), number(state["zoom"]), SCREEN)
    capture(shell, scene, "sharp")
    set_style(shell, "standard")
    capture(shell, scene, "standard")
    set_style(shell, "text")
    sharp = in_between_fraction(crop(scene.image("sharp"), box))
    standard = in_between_fraction(crop(scene.image("standard"), box))
    assert sharp <= standard * 2 / 3, f"{sharp:.3f} in between, against GNOME's {standard:.3f}"


@when(parsers.parse("the zoomed screen is captured twice, {gap_ms:d} ms apart"))
def captured_twice(shell: Shell, scene: Scene, gap_ms: int) -> None:
    capture(shell, scene, "first")
    time.sleep(gap_ms / 1000)
    capture(shell, scene, "second")


def bar_x(scene: Scene, name: str) -> float:
    """The middle of the dark bar in a capture's row through it, on screen."""
    row_y = SCREEN[1] / 2 + (BAR_Y - scene.pointer[1]) * scene.zoom
    row = luma(scene.captures[name])[int(row_y)]
    dark = np.nonzero(row < 0.5)[0]
    assert dark.size, f"no bar in the {name} capture"
    return float(dark.mean())


@then(parsers.parse("the moving bar is at least {distance:d} pixels from where it was"))
def bar_moved(scene: Scene, distance: int) -> None:
    moved = abs(bar_x(scene, "second") - bar_x(scene, "first"))
    assert moved >= distance, f"the bar moved {moved:.0f} pixels"
