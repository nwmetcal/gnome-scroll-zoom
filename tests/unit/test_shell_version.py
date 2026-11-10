# SPDX-License-Identifier: GPL-2.0-or-later
"""The test shell runs on a GNOME Shell whose major metadata.json lists, and says why not on
any other (decision 0008)."""

import os
from collections.abc import Callable
from pathlib import Path

import pytest

from tests.shell import gnome_shell_refusal

type Install = Callable[[str], None]


@pytest.fixture
def gnome_shell(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Install:
    """Put a stand-in gnome-shell that reports a version first on PATH."""

    def install(version: str) -> None:
        stand_in = tmp_path / "bin" / "gnome-shell"
        stand_in.parent.mkdir(exist_ok=True)
        stand_in.write_text(f'#!/bin/sh\necho "GNOME Shell {version}"\n')
        stand_in.chmod(0o755)
        monkeypatch.setenv("PATH", f"{stand_in.parent}{os.pathsep}{os.environ['PATH']}")

    return install


def test_a_listed_major_runs(gnome_shell: Install) -> None:
    gnome_shell("50.1")
    assert gnome_shell_refusal() is None


def test_an_unlisted_major_says_what_is_listed(gnome_shell: Install) -> None:
    gnome_shell("51.rc")
    refusal = gnome_shell_refusal()
    assert refusal is not None
    assert "51.rc" in refusal and "50" in refusal and "0008" in refusal, refusal


def test_a_major_that_only_starts_like_a_listed_one_is_refused(gnome_shell: Install) -> None:
    gnome_shell("500.0")
    assert gnome_shell_refusal() is not None


def test_no_gnome_shell_says_so(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PATH", str(tmp_path))
    refusal = gnome_shell_refusal()
    assert refusal is not None and "no GNOME Shell" in refusal, refusal
