# SPDX-License-Identifier: GPL-2.0-or-later
"""SZ-007: GNOME's keyboard zoom glides too."""

import math

from pytest_bdd import parsers, scenarios, then, when

from tests.requirements.conftest import Scene
from tests.shell import Shell, number

scenarios("SZ-007-gnome-s-keyboard-zoom-glides-too.feature")


@when(parsers.parse("GNOME's zoom level is set to {zoom:g}x, as its keyboard shortcut does"))
def set_level(shell: Shell, scene: Scene, zoom: float) -> None:
    shell.call("return scrollZoomTest.record();")
    shell.call(
        "new imports.gi.Gio.Settings({schema_id: 'org.gnome.desktop.a11y.magnifier'})"
        f".set_double('mag-factor', {zoom}); return true;"
    )
    shell.settle()
    frames = shell.call("return scrollZoomTest.stopRecording();")
    assert isinstance(frames, list)
    scene.frames = [f for f in frames if isinstance(f, dict)]


def zooms(scene: Scene) -> list[float]:
    return [number(f["zoom"]) for f in scene.frames]


@then("no frame on the way covered more than a fifth of the change")
def no_jump(scene: Scene) -> None:
    # In log terms, so a step at 2x counts the same as one at 12x.
    values = [math.log(v) for v in zooms(scene)]
    change = abs(values[-1] - values[0])
    biggest = max(abs(b - a) for a, b in zip(values, values[1:], strict=False))
    assert biggest <= change / 5, f"one frame covered {biggest / change:.0%} of the change"


@then(parsers.parse("it took at least {count:d} frames to get there"))
def took_frames(scene: Scene, count: int) -> None:
    values = zooms(scene)
    between = [v for v in values if min(values) < v < max(values)]
    assert len(between) >= count, f"{len(between)} frames between the levels"
