# SPDX-License-Identifier: GPL-2.0-or-later
"""No tracked file is over 1 MB."""

from tests.paths import ROOT
from tests.style.test_words import tracked_paths

LIMIT_BYTES = 1024 * 1024


def test_no_tracked_file_is_over_1_mb() -> None:
    large = [
        f"{path}: {(ROOT / path).stat().st_size / 1024:.0f} KB"
        for path in tracked_paths()
        if (ROOT / path).stat().st_size > LIMIT_BYTES
    ]
    assert not large, large
