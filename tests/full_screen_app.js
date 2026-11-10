// SPDX-License-Identifier: GPL-2.0-or-later
// A full-screen app for SZ-008: text, and a bar that moves every frame, as a game or a video
// keeps drawing. With --take-shortcuts it asks GNOME to let it take over the keyboard's
// shortcuts, as a virtual machine, a remote desktop, or a game that grabs the keyboard does.
//
// Run inside the test shell:  dev/test-shell.sh client gjs -m tests/full_screen_app.js
// As an X11 app, through the test shell's Xwayland: GDK_BACKEND=x11, and the DISPLAY and
// XAUTHORITY the test shell's own environment holds (scrollZoomTest.xDisplay()).
import Gdk from 'gi://Gdk?version=4.0';
import Gtk from 'gi://Gtk?version=4.0';

export const TITLE = 'Full-screen test app';
// Where things are on the screen, in pixels; the window fills it from the top-left corner.
export const TEXT = {x: 120, y: 120};
export const BAR = {left: 500, travel: 280, y: 600, width: 20, height: 40, speedPxPerMs: 0.1};

const takeShortcuts = ARGV.includes('--take-shortcuts');
const app = new Gtk.Application({application_id: 'dev.scrollzoom.FullScreen'});

app.connect('activate', () => {
    const css = new Gtk.CssProvider();
    css.load_from_string('window { background: white; color: #1a1a1a; }');
    Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), css,
        Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION);

    const overlay = new Gtk.Overlay();
    overlay.set_child(new Gtk.Label({
        label: Array(6).fill('The quick brown fox jumps over the lazy dog 0123456789').join('\n'),
        halign: Gtk.Align.START, valign: Gtk.Align.START,
        margin_start: TEXT.x, margin_top: TEXT.y,
    }));

    // A sawtooth that goes round every 2.8 s, so two moments from 300 ms to 2.5 s apart find
    // the bar at least 30 pixels apart, 90 pixels of the screen at 3x.
    const bar = new Gtk.DrawingArea({hexpand: true, vexpand: true});
    bar.set_draw_func((_area, cr) => {
        const ms = (bar.get_frame_clock()?.get_frame_time() ?? 0) / 1000;
        cr.setSourceRGB(0.1, 0.1, 0.1);
        cr.rectangle(BAR.left + (ms * BAR.speedPxPerMs) % BAR.travel, BAR.y, BAR.width, BAR.height);
        cr.fill();
    });
    bar.add_tick_callback(() => {
        bar.queue_draw();
        return true;
    });
    overlay.add_overlay(bar);

    const window = new Gtk.ApplicationWindow({application: app, title: TITLE, child: overlay});
    window.connect('notify::fullscreened', () => {
        if (takeShortcuts && window.fullscreened)
            window.get_surface().inhibit_system_shortcuts(null);
    });
    window.fullscreen();
    window.present();
});
app.run([]);
