# SPDX-License-Identifier: GPL-2.0-or-later
"""SZ-002: zoom glides from level to level."""

import math
from dataclasses import dataclass, field

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from tests.motion import Frame, Plan, biggest_step_percent, play

scenarios("SZ-002-zoom-glides-from-level-to-level.feature")

STEP = 1.2


@dataclass
class Run:
    plan: Plan = field(default_factory=Plan)
    frames: list[Frame] = field(default_factory=list[Frame])
    mark_ms: float = 0.0

    def at(self, ms: float) -> Frame:
        """The last frame at or before a time."""
        return [frame for frame in self.frames if frame.ms <= ms][-1]


@pytest.fixture
def run() -> Run:
    return Run()


@given(parsers.parse("the zoom is at {zoom:g}x"))
def zoom_at(run: Run, zoom: float) -> None:
    run.plan.start = zoom


@when(parsers.re(r"the wheel turns (?P<notches>\d+) notch(?:es)? (?P<direction>up|down)$"))
def turn(run: Run, notches: str, direction: str) -> None:
    count = int(notches)
    run.plan.add(100, "wheel", count if direction == "up" else -count)
    run.mark_ms = 100
    run.frames = play(run.plan)


@when(parsers.parse("the wheel turns {notches:d} notches up, {gap_ms:d} ms apart"))
def turn_apart(run: Run, notches: int, gap_ms: int) -> None:
    for index in range(notches):
        run.plan.add(100 + index * gap_ms, "wheel", 1)
    run.plan.seconds = 1.5 + notches * gap_ms / 1000
    run.frames = play(run.plan)


@when(
    parsers.parse("the wheel turns {up:d} notches up and, {gap_ms:d} ms later, {down:d} notch down")
)
def turn_back(run: Run, up: int, gap_ms: int, down: int) -> None:
    run.plan.add(100, "wheel", up)
    run.plan.add(100 + gap_ms, "wheel", -down)
    run.mark_ms = 100 + gap_ms
    run.frames = play(run.plan)


@when(
    parsers.parse(
        "two fingers swipe up at {speed:g} levels a second for {duration_ms:d} ms and lift"
    )
)
def swipe(run: Run, speed: float, duration_ms: int) -> None:
    gap_ms = 10
    for index in range(duration_ms // gap_ms):
        run.plan.add(100 + index * gap_ms, "touch", speed * gap_ms / 1000)
    run.mark_ms = 100 + duration_ms
    run.plan.add(run.mark_ms, "lift")
    run.plan.seconds = 3.0
    run.frames = play(run.plan)


@when("the wheel turns 1 notch up and the next frame comes 500 ms late")
def late_frame(run: Run) -> None:
    run.plan.add(1, "wheel", 1)
    run.plan.stalls.append({"frame": 1, "ms": 500})
    run.plan.seconds = 0.05
    run.frames = play(run.plan)


@then(parsers.parse("the zoom comes to rest at {zoom:g}x"))
def rests_at(run: Run, zoom: float) -> None:
    last = run.frames[-1]
    assert last.settled, f"still moving at {last.zoom:.4f}x"
    assert abs(last.zoom / zoom - 1) < 0.001, f"rests at {last.zoom:.4f}x"


@then(parsers.parse("the zoom comes to rest above {zoom:g}x"))
def rests_above(run: Run, zoom: float) -> None:
    last = run.frames[-1]
    assert last.settled and last.zoom > zoom, f"rests at {last.zoom:.3f}x"


@then(parsers.parse("no frame changes the zoom by more than {percent:g} percent"))
def no_jump(run: Run, percent: float) -> None:
    biggest = biggest_step_percent(run.frames)
    assert biggest <= percent, f"a frame changed the zoom by {biggest:.2f}%"


@then(
    parsers.parse(
        "the zoom is {share:d} percent of the way there"
        " between {low:d} and {high:d} ms after the notch"
    )
)
def most_of_the_way(run: Run, share: int, low: int, high: int) -> None:
    start, end = math.log(run.plan.start), math.log(run.frames[-1].zoom)
    there = [f for f in run.frames if (math.log(f.zoom) - start) >= share / 100 * (end - start)]
    reached_ms = there[0].ms - run.mark_ms
    assert low <= reached_ms <= high, f"{share}% of the way after {reached_ms:.0f} ms"


@then("the zoom comes to rest one step below where it was when the wheel turned back")
def rests_one_below(run: Run) -> None:
    turned = run.at(run.mark_ms).zoom
    last = run.frames[-1]
    assert last.settled
    assert abs(last.zoom / (turned / STEP) - 1) < 0.01, f"{last.zoom:.4f}x, turned at {turned:.4f}x"


@then(
    parsers.parse(
        "the zoom keeps going after the lift, to between {low:g} and {high:g} times where it was"
    )
)
def coasts(run: Run, low: float, high: float) -> None:
    ratio = run.frames[-1].zoom / run.at(run.mark_ms).zoom
    assert low <= ratio <= high, f"coasted {ratio:.3f} times further"


@then(parsers.parse("the zoom comes to rest within {seconds:g} seconds of the lift"))
def rests_soon(run: Run, seconds: float) -> None:
    resting = next(f for f in run.frames if f.ms > run.mark_ms and f.settled)
    assert resting.ms - run.mark_ms <= seconds * 1000, (
        f"rested {resting.ms - run.mark_ms:.0f} ms after"
    )


@then("the zoom comes to rest where it was at the lift")
def no_coast(run: Run) -> None:
    lifted = run.at(run.mark_ms).zoom
    last = run.frames[-1]
    assert last.settled and abs(last.zoom / lifted - 1) < 0.005, (
        f"{last.zoom:.4f}x, lifted at {lifted:.4f}x"
    )


@then("that frame moves the zoom less than half a step")
def small_move(run: Run) -> None:
    moved = math.log(run.frames[0].zoom / run.plan.start) / math.log(STEP)
    assert moved < 0.5, f"moved {moved:.2f} of a step"
