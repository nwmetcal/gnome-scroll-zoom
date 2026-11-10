#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-2.0-or-later
# A private, headless GNOME Shell for testing Scroll Zoom without logging out.
#
# It runs on its own D-Bus session with its own config, data and runtime
# folders, so it never touches the real desktop's settings or windows.
# A tiny helper extension turns on the shell's "unsafe mode" inside this test
# shell only, which lets us run JavaScript in it (Eval) and take screenshots.
#
#   dev/test-shell.sh start [WxH]     start (or restart) the test shell
#   dev/test-shell.sh eval 'js code'  run JavaScript inside it, print the result
#   dev/test-shell.sh shot out.png    screenshot the whole test screen
#   dev/test-shell.sh client cmd...   run an app inside it: Wayland, or X11 through Xwayland
#                                     with the shell's DISPLAY and XAUTHORITY (see
#                                     scrollZoomTest.xDisplay() in tests/shell_harness.js)
#   dev/test-shell.sh log             show the shell's log
#   dev/test-shell.sh stop
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(dirname "$HERE")"
ROOT="${TEST_SHELL_ROOT:-${XDG_RUNTIME_DIR:-/tmp}/scroll-zoom-test-shell}"
UUID=scroll-zoom@nhicc
HELPER=test-unsafe-mode@scroll-zoom.dev
# Wayland socket paths must stay under 108 bytes, so the runtime folder lives at a short path
# of its own, named for the root, so test shells with different roots run side by side, as
# reviewers' do.
RUN="${XDG_RUNTIME_DIR:-/tmp}/szt-$(printf '%s' "$ROOT" | sha1sum | cut -c1-10)"

test_env() {
    env -i HOME="$HOME" PATH="$PATH" LANG="${LANG:-C.UTF-8}" \
        XDG_CONFIG_HOME="$ROOT/config" XDG_DATA_HOME="$ROOT/data" \
        XDG_CACHE_HOME="$ROOT/cache" XDG_STATE_HOME="$ROOT/state" \
        XDG_RUNTIME_DIR="$RUN" \
        DBUS_SESSION_BUS_ADDRESS="$(cat "$ROOT/bus" 2>/dev/null || true)" \
        WAYLAND_DISPLAY=wayland-test GDK_BACKEND=wayland GDK_DEBUG=no-portals \
        "$@"
}

shell_call() {
    test_env gdbus call --session --dest org.gnome.Shell "$@"
}

stop() {
    if [[ -f "$ROOT/pid" ]]; then
        kill "$(cat "$ROOT/pid")" 2>/dev/null || true
        for _ in $(seq 50); do kill -0 "$(cat "$ROOT/pid")" 2>/dev/null || break; sleep 0.1; done
        rm -f "$ROOT/pid"
    fi
    # A portal started by a test app can leave a FUSE mount behind.
    fusermount3 -u -z "$RUN/doc" 2>/dev/null || fusermount -u -z "$RUN/doc" 2>/dev/null || true
    rm -rf "$RUN"
}

start() {
    local size="${1:-1280x800}"
    stop
    rm -rf "$ROOT" "$RUN"
    mkdir -p "$ROOT"/{config,data/gnome-shell/extensions,cache,state} "$RUN"
    chmod 700 "$RUN"
    # Text antialiased in gray, as GTK draws it. The machine's fontconfig may ask for subpixel
    # antialiasing instead, whose colored fringes smoothing does not yet read as text.
    mkdir -p "$ROOT/config/fontconfig"
    cat > "$ROOT/config/fontconfig/fonts.conf" <<'EOF'
<?xml version="1.0"?>
<!DOCTYPE fontconfig SYSTEM "urn:fontconfig:fonts.dtd">
<fontconfig>
  <match target="font">
    <edit name="rgba" mode="assign"><const>none</const></edit>
    <edit name="lcdfilter" mode="assign"><const>lcdnone</const></edit>
  </match>
</fontconfig>
EOF

    cp -r "$REPO/$UUID" "$ROOT/data/gnome-shell/extensions/"
    glib-compile-schemas "$ROOT/data/gnome-shell/extensions/$UUID/schemas"
    mkdir -p "$ROOT/data/gnome-shell/extensions/$HELPER"
    cat > "$ROOT/data/gnome-shell/extensions/$HELPER/metadata.json" <<EOF
{"uuid": "$HELPER", "name": "Test unsafe mode", "description": "Test shell only", "shell-version": ["50"]}
EOF
    cat > "$ROOT/data/gnome-shell/extensions/$HELPER/extension.js" <<'EOF'
import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';
export default class extends Extension {
    enable() { global.context.unsafe_mode = true; }
    disable() {}
}
EOF

    # The launcher writes the private bus address, applies test settings, then
    # becomes the shell, so its PID is the shell's PID.
    cat > "$ROOT/launch.sh" <<EOF
#!/usr/bin/env bash
echo "\$DBUS_SESSION_BUS_ADDRESS" > "$ROOT/bus"
gsettings set org.gnome.shell enabled-extensions "['$HELPER', '$UUID']"
gsettings set org.gnome.desktop.interface enable-animations false
gsettings set org.gnome.desktop.interface enable-hot-corners false
gsettings set org.gnome.desktop.interface font-antialiasing rgba
gsettings set org.gnome.desktop.interface font-hinting slight
gsettings set org.gnome.desktop.a11y.magnifier mouse-tracking proportional
echo \$\$ > "$ROOT/pid"
exec gnome-shell --headless --wayland --wayland-display wayland-test --virtual-monitor $size
EOF
    chmod +x "$ROOT/launch.sh"
    test_env setsid dbus-run-session -- "$ROOT/launch.sh" > "$ROOT/shell.log" 2>&1 &

    for _ in $(seq 150); do
        if [[ -s "$ROOT/bus" ]] && shell_call --object-path /org/gnome/Shell \
            --method org.gnome.Shell.Eval 'Main.layoutManager._startingUp === false' 2>/dev/null |
            grep -q "true, 'true'"; then
            # Leave the overview the shell opens at startup.
            shell_call --object-path /org/gnome/Shell --method org.gnome.Shell.Eval \
                'Main.overview.hide(); "ok"' > /dev/null
            echo "Test shell running ($size). Log: $ROOT/shell.log"
            return 0
        fi
        # A shell that has exited will not come up; say why now rather than at the timeout.
        if [[ -s "$ROOT/pid" ]] && ! kill -0 "$(cat "$ROOT/pid")" 2>/dev/null; then
            echo "Test shell exited. Log:" >&2
            tail -40 "$ROOT/shell.log" >&2
            return 1
        fi
        sleep 0.2
    done
    echo "Test shell did not come up. Log:" >&2
    tail -40 "$ROOT/shell.log" >&2
    return 1
}

case "${1:-}" in
start) shift; start "$@" ;;
stop) stop ;;
eval)
    shift
    shell_call --object-path /org/gnome/Shell --method org.gnome.Shell.Eval "$1"
    ;;
shot)
    out="$(realpath -m "$2")"
    shell_call --object-path /org/gnome/Shell/Screenshot \
        --method org.gnome.Shell.Screenshot.Screenshot false false "$out" > /dev/null
    echo "$out"
    ;;
client)
    shift
    test_env setsid "$@" >> "$ROOT/client.log" 2>&1 &
    ;;
log) cat "$ROOT/shell.log" ;;
*) sed -n '3,/^set -euo pipefail/{/^set -euo pipefail/!p}' "$0"; exit 1 ;;
esac
