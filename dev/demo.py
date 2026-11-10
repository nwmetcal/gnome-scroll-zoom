#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Make the README's animation: zoom gliding in on a window of text, in the test shell.

    uv run python dev/demo.py

Writes docs/scroll-zoom-demo.gif, which plays once and stops on the zoomed text, and
docs/scroll-zoom-demo-still.png, its last frame, for readers who ask for reduced motion.
Each frame is drawn at an exact zoom level, so the animation shows what the extension draws
at each step of a glide, at an even pace.
"""

import math
import sys
import time
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.shell import ROOT, SCREEN, Shell, new_root

DOCS = ROOT / "docs"
# Where to zoom: the word "crisp" in the second paragraph of dev/demo-window.js.
TARGET = (557.0, 441.0)
ZOOM = 4.0
GLIDE_FRAMES = 30
FRAME_MS = 45
HOLD_MS = 3000
# The part of the screen the animation shows, around the pointer, in pixels.
CROP = (800, 450)
# Fewer colors keep the file small; text needs few.
COLORS = 48


def eased(t: float) -> float:
    """Ease in and out, as a glide starts and settles."""
    return 0.5 - 0.5 * math.cos(math.pi * t)


def main() -> None:
    shell = Shell(new_root())
    shell.start(pattern=False)
    try:
        shell.client("gjs", "-m", str(ROOT / "dev" / "demo-window.js"))
        shell.wait_until(
            "global.get_window_actors().some(a => a.meta_window.get_title() === 'Reading')"
        )
        # Close the overview and any notification, such as the test shell's own.
        shell.call(
            "Main.overview.hide(); Main.messageTray.getSources().forEach(s => s.destroy());"
            " return true;"
        )
        x, y = TARGET
        # GNOME's default tracking keeps the point under the pointer still as zoom grows.
        shell.call(
            "scrollZoomTest.reset(); scrollZoomTest.moveTo("
            f"{x}, {y}); new imports.gi.Gio.Settings({{schema_id: "
            "'org.gnome.desktop.a11y.magnifier'}).set_string('mouse-tracking', 'proportional');"
            " return true;"
        )
        shell.wait_until(f"scrollZoomTest.state().pointer.join() === '{int(x)},{int(y)}'")
        shell.call("Main.overview.hide(); return scrollZoomTest.zoomTo(1.0);")
        time.sleep(1.0)

        frames: list[Image.Image] = []
        width, height = SCREEN
        left = min(max(int(x) - CROP[0] // 2, 0), width - CROP[0])
        top = min(max(int(y) - CROP[1] // 2, 0), height - CROP[1])
        for index in range(GLIDE_FRAMES + 1):
            level = math.exp(math.log(ZOOM) * eased(index / GLIDE_FRAMES))
            shell.call(
                "const r = Main.magnifier.getZoomRegions()[0];"
                f"r._changeROI({{xMagFactor: {level}, yMagFactor: {level},"
                " redoCursorTracking: true, animate: false}); return true;"
            )
            time.sleep(0.15)
            shot = Image.open(shell.screenshot(f"demo-{index:02d}")).convert("RGB")
            frames.append(shot.crop((left, top, left + CROP[0], top + CROP[1])))

        frames[-1].save(DOCS / "scroll-zoom-demo-still.png", optimize=True)
        # The first frame rests a moment at 1x, so the eye finds the text before it grows.
        durations = [900] + [FRAME_MS] * (len(frames) - 2) + [HOLD_MS]
        paletted = [f.quantize(colors=COLORS, method=Image.Quantize.MEDIANCUT) for f in frames]
        # No loop count: a GIF without one plays once and stops on its last frame.
        paletted[0].save(
            DOCS / "scroll-zoom-demo.gif",
            save_all=True,
            append_images=paletted[1:],
            duration=durations,
            optimize=True,
            disposal=1,
        )
    finally:
        shell.stop()
    for name in ("scroll-zoom-demo.gif", "scroll-zoom-demo-still.png"):
        print(DOCS / name, f"{(DOCS / name).stat().st_size / 1024:.0f} KB")


if __name__ == "__main__":
    main()
