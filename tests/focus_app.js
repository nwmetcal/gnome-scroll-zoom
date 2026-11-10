// SPDX-License-Identifier: GPL-2.0-or-later
// A full-screen app for SZ-009: a button at the top left, where the zoomed view starts, a
// button near the middle of the screen, and a line of text below it, both out of that view at
// 3x. Tab moves keyboard focus from the first button to the second. With --print the line
// takes focus and the app moves its text cursor on its own every 250 ms, as a terminal does
// as it prints.
//
// Run inside the test shell:  dev/test-shell.sh client gjs -m tests/focus_app.js
import Gdk from 'gi://Gdk?version=4.0';
import GLib from 'gi://GLib';
import Gtk from 'gi://Gtk?version=4.0';

export const TITLE = 'Focus test app';
// Where things are on the screen, in pixels; the window fills it from the top-left corner.
export const NEAR = {x: 40, y: 40, width: 120, height: 40};
export const MIDDLE = {x: 700, y: 380, width: 120, height: 40};
export const LINE = {x: 740, y: 560, width: 40, height: 24};
const PRINT_MS = 250;

const printing = ARGV.includes('--print');
const app = new Gtk.Application({application_id: 'dev.scrollzoom.Focus'});

app.connect('activate', () => {
    const css = new Gtk.CssProvider();
    css.load_from_string('window { background: white; color: #1a1a1a; }');
    Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), css,
        Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION);

    const fixed = new Gtk.Fixed();
    const place = (widget, box) => {
        widget.set_size_request(box.width, box.height);
        fixed.put(widget, box.x, box.y);
    };
    const near = new Gtk.Button({label: 'Near'});
    const middle = new Gtk.Button({label: 'Middle'});
    const line = new Gtk.TextView({monospace: true, top_margin: 0, left_margin: 0});
    place(near, NEAR);
    place(middle, MIDDLE);
    place(line, LINE);

    const window = new Gtk.ApplicationWindow({application: app, title: TITLE, child: fixed});
    window.fullscreen();
    window.present();

    if (!printing) {
        near.grab_focus();
        return;
    }
    // GTK gives no place for a text cursor after the last character, and GNOME skips a cursor
    // with no place, so the cursor moves between the two characters, as a terminal's cursor
    // sits on a cell.
    const buffer = line.get_buffer();
    buffer.set_text('ab', -1);
    line.grab_focus();
    let offset = 0;
    GLib.timeout_add(GLib.PRIORITY_DEFAULT, PRINT_MS, () => {
        offset = 1 - offset;
        buffer.place_cursor(buffer.get_iter_at_offset(offset));
        return GLib.SOURCE_CONTINUE;
    });
});

app.run([]);
