# SPDX-License-Identifier: GPL-2.0-or-later
"""A test shell that fails to start says why, and its log outlives it."""

import os
import shutil
from pathlib import Path

import pytest

from tests.shell import Shell, ShellError, new_root

CAUSE = "FAKE-CAUSE: no render node for the test shell"


@pytest.fixture
def failing_gnome_shell(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A stand-in gnome-shell, first on PATH, that fails to start and says why."""
    if shutil.which("dbus-run-session") is None:
        pytest.skip("the test shell's launcher needs dbus-run-session")
    stand_in = tmp_path / "bin" / "gnome-shell"
    stand_in.parent.mkdir()
    stand_in.write_text(f'#!/bin/sh\necho "{CAUSE}" >&2\nexit 1\n')
    stand_in.chmod(0o755)
    monkeypatch.setenv("PATH", f"{stand_in.parent}{os.pathsep}{os.environ['PATH']}")


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
