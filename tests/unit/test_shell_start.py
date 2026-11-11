# SPDX-License-Identifier: GPL-2.0-or-later
"""A test shell that fails to start says why, soon, and its log outlives it."""

import os
import shutil
import time
from pathlib import Path

import pytest

from tests.shell import Shell, ShellError, new_root

CAUSE = "FAKE-CAUSE: no render node for the test shell"
# Well under the 30 s dev/test-shell.sh waits for a shell that neither comes up nor exits.
SOON_S = 10


def stand_in_gnome_shell(folder: Path, monkeypatch: pytest.MonkeyPatch, then: str) -> None:
    """A stand-in gnome-shell, first on PATH, that says why it fails, then does `then`."""
    if shutil.which("dbus-run-session") is None:
        pytest.skip("the test shell's launcher needs dbus-run-session")
    stand_in = folder / "bin" / "gnome-shell"
    stand_in.parent.mkdir()
    stand_in.write_text(f'#!/bin/sh\necho "{CAUSE}" >&2\n{then}\n')
    stand_in.chmod(0o755)
    monkeypatch.setenv("PATH", f"{stand_in.parent}{os.pathsep}{os.environ['PATH']}")


@pytest.fixture
def failing_gnome_shell(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A stand-in gnome-shell that exits at once."""
    stand_in_gnome_shell(tmp_path, monkeypatch, "exit 1")


@pytest.fixture
def silent_gnome_shell(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A stand-in gnome-shell that stays up and never answers, as a shell that hangs does."""
    stand_in_gnome_shell(tmp_path, monkeypatch, "exec sleep 120")


# Takes GNOME Shell's name on the bus and offers its Eval on a main loop it never runs, so a
# call to it waits, as one to a shell that froze while starting does.
FROZEN = """
import Gio from 'gi://Gio';
import GLib from 'gi://GLib';

const bus = Gio.bus_get_sync(Gio.BusType.SESSION, null);
const xml = '<node><interface name="org.gnome.Shell"><method name="Eval"><arg type="s" ' +
    'direction="in"/><arg type="b" direction="out"/><arg type="s" direction="out"/></method>' +
    '</interface></node>';
Gio.DBusExportedObject.wrapJSObject(xml, {Eval: () => [true, '']}).export(bus, '/org/gnome/Shell');
bus.call_sync('org.freedesktop.DBus', '/org/freedesktop/DBus', 'org.freedesktop.DBus',
    'RequestName', new GLib.Variant('(su)', ['org.gnome.Shell', 0]), null, 0, -1, null);
GLib.usleep(120 * 1000000);
"""


@pytest.fixture
def frozen_gnome_shell(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A stand-in gnome-shell that holds GNOME Shell's name on the bus and never answers."""
    if shutil.which("gjs") is None:
        pytest.skip("the frozen stand-in runs in gjs")
    script = tmp_path / "frozen.js"
    script.write_text(FROZEN)
    stand_in_gnome_shell(tmp_path, monkeypatch, f"exec gjs -m {script}")


@pytest.mark.usefixtures("failing_gnome_shell")
def test_a_shell_that_fails_to_start_says_why() -> None:
    shell = Shell(new_root())
    try:
        with pytest.raises(ShellError, match="FAKE-CAUSE"):
            shell.start()
    finally:
        shell.stop()


@pytest.mark.usefixtures("failing_gnome_shell")
def test_a_stopped_shell_keeps_its_log() -> None:
    shell = Shell(new_root())
    with pytest.raises(ShellError):
        shell.start()
    log = shell.stop()
    assert CAUSE in log.read_text(), f"{log} lost the cause"
    assert not shell.root.exists()


@pytest.mark.usefixtures("failing_gnome_shell")
def test_a_shell_that_exits_is_given_up_on_at_once(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TEST_SHELL_START_S", raising=False)
    shell = Shell(new_root())
    began = time.monotonic()
    try:
        with pytest.raises(ShellError, match="FAKE-CAUSE"):
            shell.start()
    finally:
        shell.stop()
    took_s = time.monotonic() - began
    assert took_s < SOON_S, f"a shell that had exited took {took_s:.1f} s to be given up on"


@pytest.mark.usefixtures("silent_gnome_shell")
def test_a_shell_that_never_comes_up_says_why_at_the_script_s_wait(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TEST_SHELL_START_S", "1")
    shell = Shell(new_root())
    began = time.monotonic()
    try:
        with pytest.raises(ShellError, match="did not come up(?s:.*)FAKE-CAUSE"):
            shell.start()
        took_s = time.monotonic() - began
    finally:
        log = shell.stop()
    assert CAUSE in log.read_text()
    assert took_s >= 1, f"the script waited {took_s:.2f} s, not the 1 s it was given"


@pytest.mark.usefixtures("silent_gnome_shell")
def test_a_shell_that_outlasts_the_run_s_wait_says_why(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TEST_SHELL_START_S", raising=False)
    monkeypatch.setattr("tests.shell.START_TIMEOUT_S", 2)
    shell = Shell(new_root())
    try:
        with pytest.raises(ShellError, match="took over 2 s to start(?s:.*)FAKE-CAUSE"):
            shell.start()
    finally:
        log = shell.stop()
    assert CAUSE in log.read_text()


@pytest.mark.usefixtures("frozen_gnome_shell")
def test_a_shell_that_holds_its_name_and_never_answers_is_given_up_on_in_time(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TEST_SHELL_START_S", "2")
    monkeypatch.setattr("tests.shell.START_TIMEOUT_S", 20)
    shell = Shell(new_root())
    began = time.monotonic()
    try:
        with pytest.raises(ShellError, match="did not come up(?s:.*)FAKE-CAUSE"):
            shell.start()
    finally:
        shell.stop()
    took_s = time.monotonic() - began
    assert took_s < SOON_S, f"a shell that never answered took {took_s:.1f} s to be given up on"
