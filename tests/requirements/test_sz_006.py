# SPDX-License-Identifier: GPL-2.0-or-later
"""SZ-006: turning the extension off hands zoom back to GNOME."""

import time

from pytest_bdd import scenarios, then, when

from tests.images import crop
from tests.requirements.conftest import REPAINT_S, Scene, capture, pattern_box, set_style
from tests.shell import Shell

scenarios("SZ-006-turning-the-extension-off-hands-zoom-back-to-gnome.feature")

UUID = "scroll-zoom@nhicc"


@when("the extension is turned off")
def turn_off(shell: Shell, scene: Scene) -> None:
    # What GNOME's own scaling draws here, to compare with once the extension is off.
    set_style(shell, "standard")
    capture(shell, scene, "standard")
    set_style(shell, "text")
    shell.call(f"Main.extensionManager.disableExtension('{UUID}'); return true;")
    time.sleep(REPAINT_S)


@when("the extension is turned on")
def turn_on(shell: Shell) -> None:
    shell.call(f"Main.extensionManager.enableExtension('{UUID}'); return true;")
    shell.wait_until("scrollZoomTest.state().extension === 1")
    time.sleep(REPAINT_S)


@then("the zoomed screen is the one GNOME's standard scaling draws")
def gnome_scaling(shell: Shell, scene: Scene) -> None:
    capture(shell, scene, "off")
    box = scene.on_screen(pattern_box(shell))
    difference = float(
        abs(crop(scene.image("off"), box) - crop(scene.image("standard"), box)).mean()
    )
    assert difference * 255 < 0.5, f"{difference * 255:.2f}/255 from GNOME's own scaling"
