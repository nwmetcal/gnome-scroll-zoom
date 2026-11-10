# SPDX-License-Identifier: GPL-2.0-or-later
"""The test shell runs on a GNOME Shell whose major metadata.json lists, and says why not on
any other (decision 0009). The majors come from metadata.json, so listing one more or one
fewer needs no edit here."""

import json
import os
from collections.abc import Callable
from pathlib import Path
from typing import cast

import pytest

from tests.paths import EXTENSION
from tests.shell import gnome_shell_refusal

type Install = Callable[[str], None]

METADATA: dict[str, object] = json.loads((EXTENSION / "metadata.json").read_text())
LISTED = [str(major) for major in cast("list[object]", METADATA["shell-version"])]
UNLISTED = str(max(int(major) for major in LISTED) + 1)


@pytest.fixture
def gnome_shell(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Install:
    """Put a stand-in gnome-shell first on PATH; its script is the body given."""

    def install(script: str) -> None:
        stand_in = tmp_path / "bin" / "gnome-shell"
        stand_in.parent.mkdir(exist_ok=True)
        stand_in.write_text(f"#!/bin/sh\n{script}\n")
        stand_in.chmod(0o755)
        monkeypatch.setenv("PATH", f"{stand_in.parent}{os.pathsep}{os.environ['PATH']}")

    return install


@pytest.mark.parametrize("major", LISTED)
def test_each_listed_major_runs(gnome_shell: Install, major: str) -> None:
    gnome_shell(f'echo "GNOME Shell {major}.1"')
    assert gnome_shell_refusal() is None


def test_an_unlisted_major_says_what_is_listed(gnome_shell: Install) -> None:
    gnome_shell(f'echo "GNOME Shell {UNLISTED}.rc"')
    refusal = gnome_shell_refusal()
    assert refusal is not None
    assert f"{UNLISTED}.rc" in refusal and "0009" in refusal, refusal
    assert all(major in refusal for major in LISTED), refusal


def test_a_major_that_only_starts_like_a_listed_one_is_refused(gnome_shell: Install) -> None:
    longer = next(f"{major}0" for major in LISTED if f"{major}0" not in LISTED)
    gnome_shell(f'echo "GNOME Shell {longer}.0"')
    assert gnome_shell_refusal() is not None


def test_a_gnome_shell_that_fails_says_how(gnome_shell: Install) -> None:
    gnome_shell('echo "FAKE-CAUSE: no display" >&2\nexit 1')
    refusal = gnome_shell_refusal()
    assert refusal is not None and "FAKE-CAUSE: no display" in refusal, refusal


def test_no_gnome_shell_says_so(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PATH", str(tmp_path))
    refusal = gnome_shell_refusal()
    assert refusal is not None and "no GNOME Shell" in refusal, refusal
