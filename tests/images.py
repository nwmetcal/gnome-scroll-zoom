# SPDX-License-Identifier: GPL-2.0-or-later
"""Measure zoomed screenshots: where a screen point lands, and how its pixels look."""

from dataclasses import dataclass
from pathlib import Path

import numpy as np
from numpy.typing import NDArray
from PIL import Image

type Gray = NDArray[np.float64]


@dataclass(frozen=True)
class Box:
    """A rectangle in pixels: left, top, width, height."""

    x: float
    y: float
    width: float
    height: float


def luma(path: Path) -> Gray:
    """A screenshot as luma from 0 (black) to 1 (white)."""
    rgb = np.asarray(Image.open(path).convert("RGB"), dtype=np.float64) / 255.0
    weights = np.array([0.2126, 0.7152, 0.0722])
    return rgb @ weights


def zoomed(source: Box, pointer: tuple[float, float], zoom: float, screen: tuple[int, int]) -> Box:
    """Where a box of the unzoomed screen lands when zoom centres on the pointer."""
    width, height = screen
    px, py = pointer
    return Box(
        width / 2 + (source.x - px) * zoom,
        height / 2 + (source.y - py) * zoom,
        source.width * zoom,
        source.height * zoom,
    )


def inset(box: Box, margin: float) -> Box:
    """A box shrunk by a margin on every side."""
    return Box(box.x + margin, box.y + margin, box.width - 2 * margin, box.height - 2 * margin)


def crop(image: Gray, box: Box) -> Gray:
    """The pixels inside a box, rounded inward to whole pixels."""
    left, top = int(np.ceil(box.x)), int(np.ceil(box.y))
    right, bottom = int(box.x + box.width), int(box.y + box.height)
    return image[top:bottom, left:right]


def in_between_fraction(pixels: Gray) -> float:
    """How much of an area is neither ink nor paper: the share of pixels between its darkest
    and lightest tone, more than a fifth of the way from each. Blur raises it."""
    low, high = float(pixels.min()), float(pixels.max())
    if high - low < 1e-6:
        return 0.0
    t = (pixels - low) / (high - low)
    return float(np.mean((t > 0.2) & (t < 0.8)))


def best_shift(a: Gray, b: Gray, reach: int = 8) -> tuple[int, int]:
    """The shift (dx, dy) of b that best lines it up with a, within `reach` pixels."""
    height, width = a.shape
    inner = a[reach : height - reach, reach : width - reach]
    best: tuple[float, int, int] | None = None
    for dy in range(-reach, reach + 1):
        for dx in range(-reach, reach + 1):
            moved = b[reach + dy : height - reach + dy, reach + dx : width - reach + dx]
            error = float(np.mean(np.abs(inner - moved)))
            if best is None or error < best[0]:
                best = (error, dx, dy)
    assert best is not None
    return best[1], best[2]


def blocks_uniform(pixels: Gray, size: int) -> float:
    """The largest spread of values inside any whole size-by-size block, aligned to the grid
    the blocks start on; 0 when every block is one flat color."""
    height, width = pixels.shape
    spread = 0.0
    for top in range(0, height - size + 1, size):
        for left in range(0, width - size + 1, size):
            block = pixels[top : top + size, left : left + size]
            spread = max(spread, float(block.max() - block.min()))
    return spread
