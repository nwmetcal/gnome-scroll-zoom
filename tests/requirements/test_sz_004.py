# SPDX-License-Identifier: GPL-2.0-or-later
"""SZ-004: zoomed text and lines are drawn sharp."""

import numpy as np
from pytest_bdd import parsers, scenarios, then, when

from tests.images import best_shift, crop, in_between_fraction, inset
from tests.requirements.conftest import Scene, capture, pattern_box, set_style
from tests.shell import Shell

scenarios("SZ-004-zoomed-text-and-lines-are-drawn-sharp.feature")

STYLES = {
    "sharp smoothing": "text",
    "soft smoothing": "soft",
    "GNOME's standard scaling": "standard",
}


@when(parsers.parse("the zoomed screen is captured with {first} and with {second}"))
def captured_with(shell: Shell, scene: Scene, first: str, second: str) -> None:
    for name in (first, second):
        set_style(shell, STYLES[name])
        capture(shell, scene, STYLES[name])


@then(
    parsers.parse(
        "the text has at most two thirds as many in-between pixels as with GNOME's scaling"
    )
)
def less_blur(shell: Shell, scene: Scene) -> None:
    box = scene.on_screen(pattern_box(shell, "text"))
    sharp = in_between_fraction(crop(scene.image("text"), box))
    standard = in_between_fraction(crop(scene.image("standard"), box))
    assert sharp <= standard * 2 / 3, f"{sharp:.3f} in between, against GNOME's {standard:.3f}"


@then(parsers.parse("the gradient differs between them by less than 1/255 on average"))
def gradient_same(shell: Shell, scene: Scene) -> None:
    # Away from the strip's own edges by more than the 4 pixels smoothing looks around: where
    # the strip meets the paper is an edge, and edges are meant to sharpen.
    box = scene.on_screen(inset(pattern_box(shell, "gradient"), 10))
    difference = np.abs(crop(scene.image("text"), box) - crop(scene.image("soft"), box))
    assert float(difference.mean()) * 255 < 1, f"{float(difference.mean()) * 255:.2f}/255"


@then("the two line up with no shift")
def line_up(shell: Shell, scene: Scene) -> None:
    box = scene.on_screen(pattern_box(shell))
    shift = best_shift(crop(scene.image("standard"), box), crop(scene.image("text"), box))
    assert shift == (0, 0), f"shifted by {shift}"
