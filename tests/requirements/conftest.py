# SPDX-License-Identifier: GPL-2.0-or-later
"""Steps the requirements that run in the test shell share."""

import time
from dataclasses import dataclass, field
from pathlib import Path

import pytest
from pytest_bdd import given, parsers, then, when

from tests.images import Box, Gray, crop, luma, zoomed
from tests.shell import SCREEN, Json, Shell, number, step

# Where the pointer rests to zoom on the test pattern: left of and above it, so the zoomed
# pointer is drawn clear of what the steps measure.
PATTERN_VIEW = (580.0, 340.0)
# How long a change of style takes to show, in seconds.
REPAINT_S = 0.6
KEY_NAMES = {"Super": "super", "Ctrl": "ctrl", "Alt": "alt", "Shift": "shift"}
MODIFIER_SETTINGS: dict[tuple[str, ...], str] = {
    ("super",): "super",
    ("super", "alt"): "super-alt",
    ("super", "ctrl"): "super-ctrl",
    ("super", "shift"): "super-shift",
}


@dataclass
class Scene:
    """What a scenario has set up and captured so far."""

    zoom: float = 1.0
    pointer: tuple[float, float] = PATTERN_VIEW
    captures: dict[str, Path] = field(default_factory=dict[str, Path])
    frames: list[dict[str, Json]] = field(default_factory=list[dict[str, Json]])

    def image(self, name: str) -> Gray:
        return luma(self.captures[name])

    def on_screen(self, source: Box) -> Box:
        return zoomed(source, self.pointer, self.zoom, SCREEN)


@pytest.fixture
def scene() -> Scene:
    return Scene()


def pattern(shell: Shell) -> dict[str, Json]:
    value = shell.call("return scrollZoomTest.PATTERN;")
    assert isinstance(value, dict)
    return value


def pattern_box(shell: Shell, part: str | None = None) -> Box:
    """A part of the test pattern, or the whole of it, on the unzoomed screen."""
    whole = pattern(shell)
    x, y = number(whole["x"]), number(whole["y"])
    if part is None:
        return Box(x, y, number(whole["width"]), number(whole["height"]))
    box = whole[part]
    assert isinstance(box, dict)
    return Box(
        x + number(box["x"]),
        y + number(box["y"]),
        number(box["width"]),
        number(box["height"]),
    )


def set_style(shell: Shell, style: str) -> None:
    shell.call(f"scrollZoomTest.settings().set_string('smoothing-style', '{style}'); return true;")
    time.sleep(REPAINT_S)


def capture(shell: Shell, scene: Scene, name: str) -> None:
    scene.captures[name] = shell.screenshot(name)


def zoom_to(shell: Shell, scene: Scene, zoom: float, pointer: tuple[float, float]) -> None:
    x, y = pointer
    shell.run_steps([step(1, "moveTo", x, y)])
    shell.wait_until(f"scrollZoomTest.state().pointer.join() === '{int(x)},{int(y)}'")
    shell.call(f"return scrollZoomTest.zoomTo({zoom});")
    shell.wait_until("scrollZoomTest.state().on")
    shell.settle()
    scene.zoom = zoom
    scene.pointer = pointer


def held(keys: str) -> list[str]:
    """'Super and Ctrl' or 'Super, Alt, and backslash' as key names."""
    words = keys.replace(",", " ").replace(" and ", " ").split()
    return [KEY_NAMES.get(word, word) for word in words]


def wheel_steps(keys: list[str], notches: int, direction: str) -> list[list[Json]]:
    sign = 1 if direction == "up" else -1
    steps: list[list[Json]] = [step(20, "press", key) for key in keys]
    steps += [step(60, "notch", sign) for _ in range(notches)]
    steps += [step(20, "release", key) for key in reversed(keys)]
    return steps


@given("zoom is off")
def zoom_is_off(shell: Shell) -> None:
    assert shell.state()["on"] is False


@given(parsers.parse("zoom is on at {zoom:g}x"))
def zoom_is_on_at(shell: Shell, scene: Scene, zoom: float) -> None:
    zoom_to(shell, scene, zoom, (640.0, 400.0))


@given(parsers.parse("zoom is on at {zoom:g}x over the test pattern"))
def zoom_over_pattern(shell: Shell, scene: Scene, zoom: float) -> None:
    zoom_to(shell, scene, zoom, PATTERN_VIEW)
    time.sleep(REPAINT_S)
    capture(shell, scene, "before")


@given(parsers.parse("the keys to hold are set to {keys}"))
def keys_to_hold(shell: Shell, keys: str) -> None:
    setting = MODIFIER_SETTINGS[tuple(held(keys))]
    shell.call(f"scrollZoomTest.settings().set_string('modifier', '{setting}'); return true;")


@when(
    parsers.re(
        r"(?P<keys>.+) (?:is|are) held and the wheel turns (?P<notches>\d+)"
        r" notch(?:es)? (?P<direction>up|down)"
    )
)
def hold_and_turn(shell: Shell, keys: str, notches: str, direction: str) -> None:
    shell.run_steps(wheel_steps(held(keys), int(notches), direction))
    time.sleep(0.2)
    shell.settle()


@when(parsers.parse("the wheel turns {notches:d} notches {direction} with no key held"))
def turn_alone(shell: Shell, notches: int, direction: str) -> None:
    shell.run_steps(wheel_steps([], notches, direction))
    time.sleep(0.3)
    shell.settle()


@when(parsers.parse("{keys} are pressed together"))
def press_together(shell: Shell, keys: str) -> None:
    names = held(keys)
    steps: list[list[Json]] = [step(20, "press", key) for key in names]
    steps += [step(20, "release", key) for key in reversed(names)]
    shell.run_steps(steps)
    time.sleep(REPAINT_S)


@then(parsers.parse("zoom is on at {zoom:g}x"))
def zoom_on_at(shell: Shell, zoom: float) -> None:
    state = shell.state()
    assert state["on"] is True, state
    assert abs(number(state["zoom"]) / zoom - 1) < 0.005, state


@then(parsers.parse("zoom is on above {zoom:g}x"))
def zoom_on_above(shell: Shell, zoom: float) -> None:
    state = shell.state()
    assert state["on"] is True, state
    assert number(state["zoom"]) > zoom, state


@then("zoom is off")
def then_zoom_off(shell: Shell) -> None:
    state = shell.state()
    assert state["on"] is False, state


@then("the zoomed text is sharp again")
def sharp_again(shell: Shell, scene: Scene) -> None:
    capture(shell, scene, "after")
    box = scene.on_screen(pattern_box(shell))
    before, after = crop(scene.image("before"), box), crop(scene.image("after"), box)
    difference = float(abs(before - after).mean()) * 255
    assert difference < 0.5, f"{difference:.2f}/255 from the sharp view it started with"
