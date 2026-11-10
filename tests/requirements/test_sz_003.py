# SPDX-License-Identifier: GPL-2.0-or-later
"""SZ-003: the zoomed view follows the pointer every frame."""

from pytest_bdd import parsers, scenarios, then, when

from tests.requirements.conftest import Scene
from tests.shell import Json, Shell, number, step

scenarios("SZ-003-the-zoomed-view-follows-the-pointer-every-frame.feature")


@when(
    parsers.parse("the pointer moves {step_px:d} pixels every {gap_ms:d} ms for {duration_ms:d} ms")
)
def pointer_moves(shell: Shell, scene: Scene, step_px: int, gap_ms: int, duration_ms: int) -> None:
    x, y = scene.pointer
    moves: list[list[Json]] = [
        step(gap_ms, "moveTo", x + (i + 1) * step_px, y + (i + 1) * step_px / 2)
        for i in range(duration_ms // gap_ms)
    ]
    shell.call("return scrollZoomTest.record();")
    shell.run_steps(moves)
    frames = shell.call("return scrollZoomTest.stopRecording();")
    assert isinstance(frames, list)
    scene.frames = [f for f in frames if isinstance(f, dict)]


@then(parsers.parse("the view moves at least {rate:d} times a second while the pointer moves"))
def view_moves(scene: Scene, rate: int) -> None:
    # A frame is drawn only when something changes, so count the view's moves over the time
    # the pointer moved, not the share of frames that moved.
    moves = [
        number(b["ms"])
        for a, b in zip(scene.frames, scene.frames[1:], strict=False)
        if a["roi"] != b["roi"]
    ]
    assert len(moves) > 1, "the view never moved"
    per_second = (len(moves) - 1) / ((moves[-1] - moves[0]) / 1000)
    assert per_second >= rate, f"the view moved {per_second:.0f} times a second"
