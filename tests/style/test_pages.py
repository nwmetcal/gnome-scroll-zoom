# SPDX-License-Identifier: GPL-2.0-or-later
"""Every image in the README and the project page says what it shows, and the page's
animation has a still for reduced motion."""

import re

from tests.paths import ROOT

README = (ROOT / "README.md").read_text()
PAGE = (ROOT / "site" / "index.html").read_text()


def test_every_readme_image_has_alt_text() -> None:
    images = re.findall(r"!\[([^\]]*)\]\(([^)]+)\)", README)
    assert images
    for alt, path in images:
        assert len(alt.split()) >= 4, f"{path}: say what the image shows"
        assert (ROOT / path).exists(), f"{path} is missing"


def test_every_page_image_has_alt_text() -> None:
    images = re.findall(r"<img\b[^>]*>", PAGE, re.S)
    assert images
    for tag in images:
        alt = re.search(r'alt="([^"]*)"', tag)
        assert alt and len(alt.group(1).split()) >= 4, f"say what this shows: {tag}"


def test_the_page_animation_has_a_still_for_reduced_motion() -> None:
    assert 'media="(prefers-reduced-motion: reduce)"' in PAGE
    for name in re.findall(r'(?:src|srcset)="([^"]+\.(?:png|gif))"', PAGE):
        assert (ROOT / "docs" / name).exists(), f"site/index.html shows {name}, not in docs/"
