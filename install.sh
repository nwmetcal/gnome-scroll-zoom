#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-2.0-or-later
# Installs the Scroll Zoom GNOME Shell extension for the current user and enables it.
set -euo pipefail

UUID=scroll-zoom@nhicc
SRC="$(cd "$(dirname "$0")" && pwd)/$UUID"
DEST="$HOME/.local/share/gnome-shell/extensions/$UUID"

rm -rf "$DEST"
mkdir -p "$DEST"
cp -r "$SRC"/. "$DEST"/
glib-compile-schemas --strict "$DEST/schemas"
echo "Installed to $DEST"

# If the running shell already knows the extension (a reinstall), this reloads it.
# A first install on Wayland isn't seen until the next login, so also add it to
# the enabled list, which the shell reads at login.
gnome-extensions enable "$UUID" 2>/dev/null || true

current=$(gsettings get org.gnome.shell enabled-extensions)
if [[ $current != *"'$UUID'"* ]]; then
    if [[ $current == "@as []" || $current == "[]" ]]; then
        updated="['$UUID']"
    else
        updated="${current%]}, '$UUID']"
    fi
    gsettings set org.gnome.shell enabled-extensions "$updated"
fi

# On Wayland the shell keeps running the code it loaded at login.
echo "Enabled. Log out and back in to load this version, then hold Super and scroll to zoom."
