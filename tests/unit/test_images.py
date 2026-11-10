# SPDX-License-Identifier: GPL-2.0-or-later
"""Measuring screenshots: a crop is wholly on the image or an error, and shapes measure as
they are drawn."""

from collections.abc import Callable

import numpy as np
import pytest

from tests.images import Box, Gray, bar_heights, corner_gaps, crop, ink, ink_amount, shrunk

IMAGE = np.zeros((800, 1280))


def test_a_box_on_the_image_crops_to_its_size() -> None:
    assert crop(IMAGE, Box(10, 20, 100, 50)).shape == (50, 100)


@pytest.mark.parametrize(
    "box",
    [
        Box(-130.0, -2.0, 993.0, 207.0),
        Box(1200, 10, 200, 10),
        Box(10, 790, 10, 20),
        Box(10, 10, 0, 10),
    ],
)
def test_a_box_not_wholly_on_the_image_is_an_error(box: Box) -> None:
    with pytest.raises(ValueError, match="not wholly on"):
        crop(IMAGE, box)


def drawn(inked: Callable[[Gray, Gray], Gray], size: tuple[int, int], zoom: float = 1) -> Gray:
    """A shape drawn on white paper in black at a zoom, each pixel the share of it the shape
    covers, from 4 by 4 samples. The shape takes points in pixels before zooming."""
    width, height = size
    x, y = np.meshgrid((np.arange(width * 4) + 0.5) / 4, (np.arange(height * 4) + 0.5) / 4)
    covered = inked(x / zoom, y / zoom).reshape(height, 4, width, 4)
    return 1.0 - covered.mean(axis=(1, 3))


def square(x: Gray, y: Gray) -> Gray:
    return ((x >= 10) & (x < 40) & (y >= 12) & (y < 50)).astype(float)


def rounded(radius: float) -> Callable[[Gray, Gray], Gray]:
    def inked(x: Gray, y: Gray) -> Gray:
        cx = np.clip(x, 10 + radius, 40 - radius)
        cy = np.clip(y, 12 + radius, 50 - radius)
        near = (x - cx) ** 2 + (y - cy) ** 2 <= radius**2
        return ((square(x, y) > 0) & near).astype(float)

    return inked


def test_ink_runs_from_the_paper_to_the_darkest_tone() -> None:
    pixels = np.array([[1.0, 0.55, 0.1]])
    assert ink(pixels)[0].tolist() == pytest.approx([0.0, 0.5, 1.0])


def test_a_wider_stroke_carries_more_ink() -> None:
    def thin(x: Gray, y: Gray) -> Gray:
        return ((x >= 10) & (x < 16)).astype(float)

    def wide(x: Gray, y: Gray) -> Gray:
        return ((x >= 10) & (x < 19)).astype(float)

    assert ink_amount(drawn(wide, (40, 20))) == pytest.approx(
        1.5 * ink_amount(drawn(thin, (40, 20)))
    )


def test_a_crisp_right_angle_has_no_gap_at_its_corners() -> None:
    assert max(corner_gaps(ink(drawn(square, (50, 60))))) < 0.5


@pytest.mark.parametrize("radius", [3.0, 6.0])
def test_a_rounded_corner_is_its_radius_times_0_41_in(radius: float) -> None:
    gaps = corner_gaps(ink(drawn(rounded(radius), (50, 60))))
    assert gaps == pytest.approx([radius * (2**0.5 - 1)] * 4, abs=0.4)


def test_a_view_shrunk_back_is_the_mean_of_each_block() -> None:
    view: Gray = np.repeat(np.repeat(np.array([[0.0, 1.0], [0.5, 0.25]]), 3, axis=0), 3, axis=1)
    view[0, 0] = 0.9
    assert shrunk(view, 3).ravel().tolist() == pytest.approx([0.1, 1.0, 0.5, 0.25])


def test_a_view_not_in_whole_blocks_is_an_error() -> None:
    with pytest.raises(ValueError, match="not whole blocks"):
        shrunk(np.zeros((7, 9)), 3)


def bar(x: Gray, y: Gray) -> Gray:
    """A flat bar half a pixel tall inside one row of pixels, 4 pixels long."""
    return ((x >= 1) & (x < 5) & (y >= 2.25) & (y < 2.75)).astype(float)


def test_a_crisp_bar_is_drawn_as_tall_as_its_ink() -> None:
    unzoomed = 1 - drawn(bar, (6, 5))
    zoomed = 1 - drawn(bar, (36, 30), zoom=6)
    heights = bar_heights(unzoomed, zoomed, 6)
    assert len(heights) == 4
    assert all(abs(shown - meant) < 0.1 for shown, meant in heights)


def test_a_bar_drawn_wide_and_pale_is_not() -> None:
    unzoomed = 1 - drawn(bar, (6, 5))
    pale = np.repeat(np.repeat(unzoomed, 6, axis=0), 6, axis=1)
    assert all(abs(shown - meant) > 1 for shown, meant in bar_heights(unzoomed, pale, 6))
