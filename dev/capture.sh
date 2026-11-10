#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-2.0-or-later
# Screenshots the test page zoomed in with each smoothing mode, for comparing.
# Needs a running test shell with the test page open (see test-shell.sh).
#
#   dev/capture.sh OUT_DIR ZOOM X Y [MODE...]
#
# X, Y is the screen point to zoom in on. MODEs: text soft standard pixels
# (default: all). Writes OUT_DIR/<mode>-<zoom>x.png.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
S="$HERE/test-shell.sh"
out="$1" zoom="$2" x="$3" y="$4"
shift 4
modes=("$@")
[[ ${#modes[@]} -gt 0 ]] || modes=(text soft standard pixels)
mkdir -p "$out"

ext='Main.extensionManager.lookup("scroll-zoom@nhicc").stateObj'
# Pointer warps apply asynchronously and occasionally land short, so warp
# until the pointer is where it should be.
for _ in 1 2 3 4 5; do
    "$S" eval "global.stage.get_context().get_backend().get_default_seat().warp_pointer($x, $y); 'ok'" > /dev/null
    sleep 0.3
    "$S" eval "JSON.stringify(global.get_pointer().slice(0, 2))" | grep -q "\\[$x,$y\\]" && break
done
"$S" eval "Main.overview.hide();
    new (imports.gi.Gio.Settings)({schema_id: 'org.gnome.desktop.a11y.magnifier'}).set_double('mag-factor', $zoom);
    new (imports.gi.Gio.Settings)({schema_id: 'org.gnome.desktop.a11y.applications'}).set_boolean('screen-magnifier-enabled', true);
    'ok'" > /dev/null
for mode in "${modes[@]}"; do
    if [[ $mode == pixels ]]; then
        settings="s.set_string('smoothing-style', 'text'); s.set_boolean('smooth-images', false);"
    else
        settings="s.set_boolean('smooth-images', true); s.set_string('smoothing-style', '$mode');"
    fi
    "$S" eval "const s = $ext._settings; $settings 'ok'" > /dev/null
    sleep 0.8
    "$S" shot "$out/$mode-${zoom}x.png" > /dev/null
    echo "$out/$mode-${zoom}x.png"
done
