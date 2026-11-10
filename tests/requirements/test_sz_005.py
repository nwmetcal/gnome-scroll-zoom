# SPDX-License-Identifier: GPL-2.0-or-later
"""SZ-005: smoothing turns off and on."""

import math
import time

from pytest_bdd import parsers, scenarios, then, when

from tests.images import Box, blocks_uniform, crop
from tests.requirements.conftest import REPAINT_S, Scene, capture, pattern_box
from tests.shell import Shell

scenarios("SZ-005-smoothing-turns-off-and-on.feature")


@when("smoothing is turned off in the settings")
def smoothing_off(shell: Shell) -> None:
    shell.call("scrollZoomTest.settings().set_boolean('smooth-images', false); return true;")
    time.sleep(REPAINT_S)


@then(
    parsers.parse(
        "every whole zoomed pixel of the pattern is one flat square of {size:d} by {size2:d}"
    )
)
def hard_squares(shell: Shell, scene: Scene, size: int, size2: int) -> None:
    assert size == size2 == round(scene.zoom)
    capture(shell, scene, "squares")
    source = pattern_box(shell)
    # Start at whole source pixels, so the squares fall on the grid of blocks.
    whole = Box(math.ceil(source.x), math.ceil(source.y), source.width - 1, source.height - 1)
    spread = blocks_uniform(crop(scene.image("squares"), scene.on_screen(whole)), size)
    assert spread * 255 < 1, f"a square spans {spread * 255:.1f}/255"
