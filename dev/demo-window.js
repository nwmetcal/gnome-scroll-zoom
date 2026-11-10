// SPDX-License-Identifier: GPL-2.0-or-later
// A window of ordinary reading text for the README's animation (dev/demo.py).
// Run inside the test shell:  dev/test-shell.sh client gjs -m dev/demo-window.js
import Gtk from 'gi://Gtk?version=4.0';
import Gdk from 'gi://Gdk?version=4.0';

const PARAGRAPHS = [
    'Small print is everywhere: settings, menus, the fine print of a form. Zoom should ' +
    'make it easy to read, not just bigger.',
    'Hold Super and scroll to zoom in on whatever is under the pointer. Scroll back out to ' +
    'return to the whole screen. The letters stay crisp at every size, so the text you ' +
    'zoomed in to read is the text you can read.',
];

const app = new Gtk.Application({application_id: 'dev.scrollzoom.Demo'});
app.connect('activate', () => {
    const css = new Gtk.CssProvider();
    css.load_from_string(`
        window { background: #fbfbfb; color: #222226; }
        .heading { font-size: 20pt; font-weight: 700; }
        .body { font-size: 11pt; }
        .caption { font-size: 9pt; color: #5e5c64; }
    `);
    Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), css,
        Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION);

    const box = new Gtk.Box({
        orientation: Gtk.Orientation.VERTICAL, spacing: 14,
        margin_start: 220, margin_end: 220, margin_top: 200,
    });
    box.append(new Gtk.Label({label: 'Reading the small print', xalign: 0, css_classes: ['heading']}));
    for (const text of PARAGRAPHS) {
        box.append(new Gtk.Label({
            label: text, xalign: 0, wrap: true, max_width_chars: 70, css_classes: ['body'],
        }));
    }
    box.append(new Gtk.Label({
        label: 'Last updated 9 November 2026 · Page 1 of 1', xalign: 0, css_classes: ['caption'],
    }));

    new Gtk.ApplicationWindow({
        application: app, title: 'Reading', default_width: 1100, default_height: 700, child: box,
    }).present();
});
app.run([]);
