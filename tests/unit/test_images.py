# SPDX-License-Identifier: GPL-2.0-or-later
"""Measuring screenshots: a crop is wholly on the image or an error."""

import numpy as np
import pytest

from tests.images import Box, crop

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
