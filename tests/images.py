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


def viewed(source: Box, view: Box, screen: tuple[int, int]) -> Box:
    """Where a box of the unzoomed screen lands when the full-screen zoomed view shows the
    part `view` of it, wherever the view is."""
    scale_x, scale_y = screen[0] / view.width, screen[1] / view.height
    return Box(
        (source.x - view.x) * scale_x,
        (source.y - view.y) * scale_y,
        source.width * scale_x,
        source.height * scale_y,
    )


def inset(box: Box, margin: float) -> Box:
    """A box shrunk by a margin on every side."""
    return Box(box.x + margin, box.y + margin, box.width - 2 * margin, box.height - 2 * margin)


def crop(image: Gray, box: Box) -> Gray:
    """The pixels inside a box, rounded inward to whole pixels. A box that is not wholly on
    the image is an error, not a smaller or empty crop, so a step never judges nothing."""
    left, top = int(np.ceil(box.x)), int(np.ceil(box.y))
    right, bottom = int(box.x + box.width), int(box.y + box.height)
    height, width = image.shape[:2]
    if left < 0 or top < 0 or right > width or bottom > height or right <= left or bottom <= top:
        raise ValueError(f"{box} is not wholly on the {width} by {height} image")
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


def ink(pixels: Gray) -> Gray:
    """How much ink each pixel carries, from 0 at the area's lightest tone (the paper) to 1 at
    its darkest (the ink)."""
    low, high = float(pixels.min()), float(pixels.max())
    if high - low < 1e-6:
        return np.zeros_like(pixels)
    return (high - pixels) / (high - low)


def ink_amount(pixels: Gray) -> float:
    """All the ink an area carries: how far each pixel is below the area's lightest tone,
    summed, so a stroke drawn heavier or wider carries more."""
    return float((pixels.max() - pixels).sum())


def _rise(profile: Gray) -> float:
    """Where a profile of ink first reaches half, in pixels from the start of its first
    pixel, between pixel centres."""
    for k in range(1, len(profile)):
        before, after = float(profile[k - 1]), float(profile[k])
        if before < 0.5 <= after:
            return k - 0.5 + (0.5 - before) / (after - before)
    raise ValueError("the ink never reaches half")


def _at(t: Gray, x: float, y: float) -> float:
    """Ink at a point between pixel centres, from the four around it."""
    height, width = t.shape
    left, top = int(np.floor(x - 0.5)), int(np.floor(y - 0.5))
    fx, fy = x - 0.5 - left, y - 0.5 - top

    def pixel(i: int, j: int) -> float:
        return float(t[min(max(j, 0), height - 1), min(max(i, 0), width - 1)])

    return (
        pixel(left, top) * (1 - fx) * (1 - fy)
        + pixel(left + 1, top) * fx * (1 - fy)
        + pixel(left, top + 1) * (1 - fx) * fy
        + pixel(left + 1, top + 1) * fx * fy
    )


def corner_gaps(t: Gray) -> list[float]:
    """For one dark rectangle on paper, as ink (see `ink`): how far in from where each pair of
    its edges meet its ink first reaches half, along the corner's diagonal, in pixels. A
    right angle drawn crisply has its half-ink outline through that point, so near 0; a corner
    rounded to a radius r is r times 0.41 in."""
    columns = np.nonzero(t.max(axis=0) >= 0.5)[0]
    rows = np.nonzero(t.max(axis=1) >= 0.5)[0]
    if len(columns) < 3 or len(rows) < 3:
        raise ValueError("no rectangle of ink to measure")
    # Each edge is found along lines through the rectangle's middle, away from its corners.
    across = range(
        columns[0] + int(0.35 * len(columns)), columns[0] + max(int(0.65 * len(columns)), 1)
    )
    down = range(rows[0] + int(0.35 * len(rows)), rows[0] + max(int(0.65 * len(rows)), 1))
    height, width = t.shape
    top = float(np.mean([_rise(t[:, x]) for x in across]))
    bottom = height - float(np.mean([_rise(t[::-1, x]) for x in across]))
    left = float(np.mean([_rise(t[y, :]) for y in down]))
    right = width - float(np.mean([_rise(t[y, ::-1]) for y in down]))
    reach = float(min(len(columns), len(rows))) / 2
    gaps: list[float] = []
    for x, inward_x in ((left, 1), (right, -1)):
        for y, inward_y in ((top, 1), (bottom, -1)):
            steps = np.arange(0.0, reach, 0.05)
            inside = [
                s
                for s in steps
                if _at(t, x + inward_x * s / np.sqrt(2), y + inward_y * s / np.sqrt(2)) >= 0.5
            ]
            gaps.append(float(inside[0]) if inside else reach)
    return gaps


def shrunk(pixels: Gray, zoom: int) -> Gray:
    """A zoomed view shrunk back to the size it was zoomed from: each pixel the mean of the
    zoom-by-zoom block it was drawn as."""
    height, width = pixels.shape
    if height % zoom or width % zoom:
        raise ValueError(f"{width} by {height} is not whole blocks of {zoom}")
    return pixels.reshape(height // zoom, zoom, width // zoom, zoom).mean(axis=(1, 3))


def _height(profile: Gray) -> float:
    """How tall the half-ink part of a profile of ink is, in pixels, between where it first
    rises through half and where it last falls through it; 0 when it never reaches half."""
    if profile.max() < 0.5:
        return 0.0
    return len(profile) - _rise(profile[::-1]) - _rise(profile)


def bar_heights(unzoomed: Gray, zoomed: Gray, zoom: int) -> list[tuple[float, float]]:
    """For each pixel of an unzoomed area, as ink (see `ink`), that is part of a thin flat
    bar, partly inked with the pixels above and below it all but empty: how tall the bar is
    drawn in the zoomed view, as ink, and how tall its ink says it is, both in zoomed pixels.
    The drawn height is the half-ink part of each column down the pixel's block and the
    empty blocks above and below it, the mean over the block's columns; a bar drawn crisply
    as tall as its ink matches, and one drawn wide and pale, or blurred, does not."""
    height, width = unzoomed.shape
    if zoomed.shape != (height * zoom, width * zoom):
        raise ValueError(f"a {zoomed.shape} view is not {zoom} times {unzoomed.shape}")
    found: list[tuple[float, float]] = []
    for y in range(1, height - 1):
        for x in range(width):
            here, above, below = unzoomed[y, x], unzoomed[y - 1, x], unzoomed[y + 1, x]
            if 0.2 <= here <= 0.95 and above < 0.1 and below < 0.1:
                block = zoomed[(y - 1) * zoom : (y + 2) * zoom, x * zoom : (x + 1) * zoom]
                drawn = float(np.mean([_height(block[:, k]) for k in range(zoom)]))
                found.append((drawn, float(here) * zoom))
    return found


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
