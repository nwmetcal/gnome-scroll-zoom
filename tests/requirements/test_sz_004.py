# SPDX-License-Identifier: GPL-2.0-or-later
"""SZ-004: zoomed text and lines are drawn sharp."""

import time

import numpy as np
from pytest_bdd import given, parsers, scenarios, then, when

from tests.images import (
    Box,
    bar_heights,
    best_shift,
    broken_pieces,
    corner_gaps,
    crop,
    far_from_ink,
    in_between_fraction,
    ink,
    ink_amount,
    inset,
    shrunk,
)
from tests.requirements.conftest import (
    PATTERN_PARTS,
    REPAINT_S,
    Scene,
    capture,
    pattern,
    pattern_box,
    set_style,
)
from tests.shell import Shell, number

scenarios("SZ-004-zoomed-text-and-lines-are-drawn-sharp.feature")

STYLES = {
    "sharp smoothing": "text",
    "soft smoothing": "soft",
    "GNOME's standard scaling": "standard",
}
# The harness draws each stem one pixel wide.
STEM_WIDTH_PX = 1.0


@given("the test pattern is captured unzoomed")
def captured_unzoomed(shell: Shell, scene: Scene) -> None:
    assert shell.state()["on"] is False
    capture(shell, scene, "unzoomed")


@given(parsers.parse("the edge position is set to {position:g}"))
def edge_position(shell: Shell, position: float) -> None:
    shell.call(f"scrollZoomTest.settings().set_double('edge-position', {position}); return true;")
    time.sleep(REPAINT_S)


@when(parsers.parse("the zoomed screen is captured with {first} and with {second}"))
def captured_with(shell: Shell, scene: Scene, first: str, second: str) -> None:
    for name in (first, second):
        set_style(shell, STYLES[name])
        capture(shell, scene, STYLES[name])


@when("the zoomed screen is captured with sharp smoothing")
def captured_sharp(shell: Shell, scene: Scene) -> None:
    set_style(shell, "text")
    capture(shell, scene, "text")


SHARES = {"two thirds": 2 / 3, "a third": 1 / 3}


@then(
    parsers.parse(
        "the {part} has at most {share} as many in-between pixels as with GNOME's scaling"
    )
)
def less_blur(shell: Shell, scene: Scene, part: str, share: str) -> None:
    box = scene.on_screen(pattern_box(shell, PATTERN_PARTS[part]))
    sharp = in_between_fraction(crop(scene.image("text"), box))
    standard = in_between_fraction(crop(scene.image("standard"), box))
    assert sharp <= standard * SHARES[share], (
        f"{sharp:.3f} in between, against GNOME's {standard:.3f}"
    )


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


@then(
    parsers.parse(
        "every corner of the two stems and the square is within {most:g} pixel of a right angle"
    )
)
def corners_square(shell: Shell, scene: Scene, most: float) -> None:
    whole = pattern(shell)
    stems = whole["stems"]
    assert isinstance(stems, dict)
    shapes = {
        name: Box(
            number(whole["x"]) + number(whole[name]),
            number(whole["y"]) + number(stems["y"]),
            STEM_WIDTH_PX,
            number(stems["height"]),
        )
        for name in ("fullStem", "splitStem")
    }
    shapes["square"] = pattern_box(shell, "square")
    for name, shape in shapes.items():
        # With a pixel of paper around it, short of the shapes beside it.
        around = inset(scene.on_screen(shape), -scene.zoom)
        gaps = corner_gaps(ink(crop(scene.image("text"), around)))
        assert max(gaps) <= most, f"{name}: corners {', '.join(f'{g:.1f}' for g in gaps)} pixels in"


@then(
    parsers.parse(
        "the {part} carries within {most:g} percent of the ink it carries with GNOME's scaling"
    )
)
def keeps_weight(shell: Shell, scene: Scene, part: str, most: float) -> None:
    box = scene.on_screen(pattern_box(shell, PATTERN_PARTS[part]))
    sharp = ink_amount(crop(scene.image("text"), box))
    standard = ink_amount(crop(scene.image("standard"), box))
    change = (sharp / standard - 1) * 100
    assert abs(change) <= most, f"{change:+.1f} percent of the ink with GNOME's scaling"


@then(
    parsers.parse(
        "shrunk back to its unzoomed size, the {part} keeps each pixel's ink within {most:g}"
        " percent on average"
    )
)
def keeps_each_pixel(shell: Shell, scene: Scene, part: str, most: float) -> None:
    source = pattern_box(shell, PATTERN_PARTS[part])
    unzoomed = crop(scene.image("unzoomed"), source)
    back = shrunk(crop(scene.image("text"), scene.on_screen(source)), round(scene.zoom))
    paper, darkest = float(unzoomed.max()), float(unzoomed.min())
    before = (paper - unzoomed) / (paper - darkest)
    after = (paper - back) / (paper - darkest)
    # Over the pixels with ink in either, so the paper around the text dilutes nothing.
    inked = (before > 0.05) | (after > 0.05)
    error = float(np.abs(after - before)[inked].mean()) * 100
    assert error <= most, f"each pixel's ink off by {error:.1f} percent on average"


# Which of a serif line's thin bars a step holds to their height: whether they ink at least
# half of each pixel.
BARS = {
    "thin bars at least half inked": True,
    "thin bars' faint ends, under half inked": False,
}


@then(
    parsers.re(
        r"its (?P<bars>.+?),? are drawn as tall as the font draws them,"
        r" within (?P<most>[\d.]+) pixel on average"
    )
)
def bars_thin(shell: Shell, scene: Scene, bars: str, most: str) -> None:
    source = pattern_box(shell, "serif")
    unzoomed = crop(scene.image("unzoomed"), source)
    zoomed = crop(scene.image("text"), scene.on_screen(source))
    paper, darkest = float(unzoomed.max()), float(unzoomed.min())
    zoom = round(scene.zoom)
    heights = [
        (shown, meant)
        for shown, meant in bar_heights(
            (paper - unzoomed) / (paper - darkest), (paper - zoomed) / (paper - darkest), zoom
        )
        if (meant / zoom >= 0.5) == BARS[bars]
    ]
    assert heights, f"no {bars} to measure"
    error = sum(abs(shown - meant) for shown, meant in heights) / len(heights)
    assert error <= float(most), (
        f"{len(heights)} {bars} drawn {error:.1f} pixels off their height on average"
    )


@then(
    parsers.parse("the paper over a pixel from the text's ink stays within {most:d}/255 of paper")
)
def paper_stays(shell: Shell, scene: Scene, most: int) -> None:
    source = pattern_box(shell, "text")
    unzoomed = crop(scene.image("unzoomed"), source)
    zoomed = crop(scene.image("text"), scene.on_screen(source))
    zoom = round(scene.zoom)
    far = np.repeat(np.repeat(far_from_ink(ink(unzoomed)), zoom, axis=0), zoom, axis=1)
    darker = (float(unzoomed.max()) - zoomed)[far] * 255
    assert float(darker.max()) <= most, (
        f"{int((darker > most).sum())} paper pixels drawn up to {float(darker.max()):.0f}/255 dark"
    )


@then("every letter GNOME's scaling draws in one piece is drawn in one piece")
def letters_whole(shell: Shell, scene: Scene) -> None:
    box = scene.on_screen(pattern_box(shell, "text"))
    broken = broken_pieces(crop(scene.image("standard"), box), crop(scene.image("text"), box))
    assert not broken, f"{len(broken)} letters drawn in {', '.join(map(str, broken))} pieces"
