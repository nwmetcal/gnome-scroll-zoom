# SPDX-License-Identifier: GPL-2.0-or-later
"""Where things are in the repository."""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REQUIREMENTS = ROOT / "requirements"
BUILD = ROOT / "build"
EXTENSION = ROOT / "scroll-zoom@nhicc"
