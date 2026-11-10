# SPDX-License-Identifier: GPL-2.0-or-later
"""Play inputs into the extension's zoom motion, outside the shell, frame by frame."""

import json
import subprocess
from dataclasses import dataclass, field

from tests.paths import ROOT

DRIVER = ROOT / "tests" / "motion_driver.js"


@dataclass
class Frame:
    ms: float
    zoom: float
    settled: bool


@dataclass
class Plan:
    """What to play: inputs at times, at a frame rate, for a while."""

    start: float = 1.0
    fps: int = 144
    seconds: float = 1.5
    inputs: list[dict[str, float | str]] = field(default_factory=list[dict[str, float | str]])
    stalls: list[dict[str, float]] = field(default_factory=list[dict[str, float]])

    def add(self, ms: float, kind: str, value: float = 0.0) -> None:
        self.inputs.append({"ms": ms, "kind": kind, "value": value})


def play(plan: Plan) -> list[Frame]:
    """Run the plan through the zoom motion and return every frame."""
    out = subprocess.run(
        ["gjs", "-m", str(DRIVER), json.dumps(plan.__dict__)],
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
    ).stdout
    rows: list[dict[str, float | bool]] = json.loads(out)
    return [Frame(float(r["ms"]), float(r["zoom"]), bool(r["settled"])) for r in rows]


def biggest_step_percent(frames: list[Frame]) -> float:
    """The largest change of zoom between two frames, in percent."""
    return max(abs(b.zoom / a.zoom - 1) * 100 for a, b in zip(frames, frames[1:], strict=False))
