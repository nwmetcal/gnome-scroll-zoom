# SPDX-License-Identifier: GPL-2.0-or-later
"""Every shell script passes shellcheck."""

import subprocess

from tests.paths import ROOT


def scripts() -> list[str]:
    found = [str(p) for p in ROOT.rglob("*.sh") if ".venv" not in p.parts]
    found += [str(p) for p in (ROOT / ".githooks").iterdir()]
    return sorted(found)


def test_shell_scripts_pass_shellcheck() -> None:
    done = subprocess.run(["shellcheck", *scripts()], capture_output=True, text=True)
    assert done.returncode == 0, done.stdout
