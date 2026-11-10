# SPDX-License-Identifier: GPL-2.0-or-later
"""Drive the private test shell (dev/test-shell.sh) from the requirements' steps."""

import json
import os
import shutil
import subprocess
import tempfile
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import cast

from tests.paths import BUILD, EXTENSION, ROOT

TEST_SHELL = ROOT / "dev" / "test-shell.sh"
HARNESS = ROOT / "tests" / "shell_harness.js"
SCREEN = (1280, 800)
# How long the zoom must hold still to count as settled, in seconds: the extension saves the
# level 0.4 s after a glide ends, and GNOME's rounding of it starts one more short glide.
STILL_S = 0.8
# The test screen refreshes as fast as the monitor this is built on, so a 60 Hz timer
# cannot pass for following every frame.
REFRESH_HZ = 144

type Json = None | bool | int | float | str | list["Json"] | dict[str, "Json"]


def number(value: Json) -> float:
    """A JSON value that must be a number."""
    assert isinstance(value, int | float) and not isinstance(value, bool), value
    return float(value)


def step(delay_ms: int, action: str, *args: Json) -> list[Json]:
    """One timed input step for the harness: after delay_ms, call action with args."""
    return [delay_ms, action, *args]


class ShellError(RuntimeError):
    """The test shell refused or failed a request."""


def gnome_shell_refusal() -> str | None:
    """Why the test shell will not run on this machine's GNOME Shell, or None when it will:
    only on a major metadata.json lists (decision 0008)."""
    try:
        done = subprocess.run(["gnome-shell", "--version"], capture_output=True, text=True)
    except FileNotFoundError:
        return "the @shell scenarios need GNOME Shell, and this machine has no GNOME Shell"
    if done.returncode != 0:
        return f"gnome-shell --version exited {done.returncode}: {done.stderr.strip()}"
    version = done.stdout.split()[-1]
    metadata: dict[str, object] = json.loads((EXTENSION / "metadata.json").read_text())
    listed = [str(major) for major in cast("list[object]", metadata["shell-version"])]
    if version.split(".")[0] in listed:
        return None
    return (
        f"the @shell scenarios run on a GNOME Shell metadata.json lists ({', '.join(listed)}),"
        f" and this machine runs {version}: to try it, list its major on a branch"
        " (decision 0008)"
    )


@dataclass
class Shell:
    """One running test shell, its root folder, and the results it writes."""

    root: Path
    _results: Path = field(init=False)

    def __post_init__(self) -> None:
        self._results = self.root / "result.json"

    def _env(self) -> dict[str, str]:
        return {**os.environ, "TEST_SHELL_ROOT": str(self.root)}

    def start(self, *, pattern: bool = True) -> None:
        """Start the shell with the extension, load the harness, and show the test pattern."""
        width, height = SCREEN
        command = [str(TEST_SHELL), "start", f"{width}x{height}@{REFRESH_HZ}"]
        try:
            done = subprocess.run(
                command, env=self._env(), capture_output=True, text=True, timeout=90
            )
        except subprocess.TimeoutExpired as timeout:
            raise ShellError(
                f"the test shell in {self.root} took over 90 s to start; its log ends:\n"
                + self._log_tail()
            ) from timeout
        if done.returncode != 0:
            raise ShellError(
                f"the test shell in {self.root} did not start:\n{done.stdout}{done.stderr}"
            )
        self.call(HARNESS.read_text())
        if pattern:
            self.call("return scrollZoomTest.showPattern();")

    def client(self, *command: str) -> None:
        """Start an app inside the shell; it keeps running until the shell stops."""
        subprocess.run([str(TEST_SHELL), "client", *command], env=self._env(), check=True)

    def stop(self) -> Path:
        """Stop the shell and remove its root, which held its settings, keeping a copy of its
        log, where GNOME Shell writes the extension's errors, beside its screenshots. Returns
        where the log is kept."""
        subprocess.run([str(TEST_SHELL), "stop"], env=self._env(), check=True, timeout=30)
        kept = self._captures() / "shell.log"
        kept.parent.mkdir(parents=True, exist_ok=True)
        log = self.root / "shell.log"
        kept.write_text(log.read_text() if log.exists() else "the shell wrote no log\n")
        shutil.rmtree(self.root)
        return kept

    def _captures(self) -> Path:
        """This shell's own folder under build/shots/, for its screenshots and its log."""
        return BUILD / "shots" / self.root.name

    def _log_tail(self, lines: int = 40) -> str:
        log = self.root / "shell.log"
        return "\n".join(log.read_text().splitlines()[-lines:]) if log.exists() else "(no log)"

    def call(self, body: str) -> Json:
        """Run JavaScript in the shell and return what its body returns, as JSON.

        The shell's Eval method answers in GVariant text, so the result comes back through a
        file instead.
        """
        self._results.unlink(missing_ok=True)
        script = (
            "(() => { const result = (() => {\n"
            f"{body}\n"
            "})(); imports.gi.GLib.file_set_contents("
            f"{json.dumps(str(self._results))}, JSON.stringify(result ?? null)); return 'ok'; }})()"
        )
        done = subprocess.run(
            [str(TEST_SHELL), "eval", script],
            env=self._env(),
            capture_output=True,
            text=True,
            timeout=30,
        )
        if done.returncode != 0 or not done.stdout.startswith("(true,"):
            raise ShellError(f"the shell refused the script: {done.stdout}{done.stderr}")
        parsed: Json = json.loads(self._results.read_text())
        return parsed

    def wait_until(self, test: str, timeout_s: float = 5.0) -> Json:
        """Poll a JavaScript expression until it is truthy, and return its value."""
        deadline = time.monotonic() + timeout_s
        while True:
            value = self.call(f"return {test};")
            if value:
                return value
            if time.monotonic() > deadline:
                raise ShellError(f"timed out after {timeout_s} s waiting for: {test}")
            time.sleep(0.05)

    def run_steps(self, steps: list[list[Json]], timeout_s: float = 10.0) -> None:
        """Run timed input steps in the shell and wait for the last one."""
        self.call(f"return scrollZoomTest.run({json.dumps(steps)});")
        self.wait_until("!scrollZoomTest.busy", timeout_s)

    def settle(self, timeout_s: float = 5.0) -> None:
        """Wait until the zoom level has stopped changing for STILL_S: longer than the
        extension waits after a glide to save the level, which GNOME rounds and hands back,
        a glide of its own."""
        deadline = time.monotonic() + timeout_s
        last = self.call("return scrollZoomTest.state().zoom;")
        still_since = time.monotonic()
        while time.monotonic() < deadline:
            time.sleep(0.1)
            now = self.call("return scrollZoomTest.state().zoom;")
            if now != last:
                last, still_since = now, time.monotonic()
            elif time.monotonic() - still_since >= STILL_S:
                return
        raise ShellError("the zoom level kept changing")

    def state(self) -> dict[str, Json]:
        """GNOME's zoom state, the overview, and the extension's state."""
        value = self.call("return scrollZoomTest.state();")
        assert isinstance(value, dict)
        return value

    def screenshot(self, name: str) -> Path:
        """A screenshot of the whole test screen, kept under build/shots/, in a folder of
        this shell's own, so runs side by side never judge each other's captures."""
        out = self._captures() / f"{name}.png"
        out.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run([str(TEST_SHELL), "shot", str(out)], env=self._env(), check=True, timeout=30)
        return out


def new_root() -> Path:
    """A fresh folder for one test shell."""
    return Path(tempfile.mkdtemp(prefix="scroll-zoom-shell-"))


def eventually(check: Callable[[], bool], timeout_s: float = 3.0) -> bool:
    """Whether `check` turns true within the timeout."""
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if check():
            return True
        time.sleep(0.05)
    return check()
