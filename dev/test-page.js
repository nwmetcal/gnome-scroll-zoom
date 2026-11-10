// SPDX-License-Identifier: GPL-2.0-or-later
// A fixed test window for judging zoom quality: text at several sizes and
// weights, light-on-dark and colored text, thin diagonal lines, and a photo.
// Run inside the test shell:  dev/test-shell.sh client gjs -m dev/test-page.js
import Gtk from 'gi://Gtk?version=4.0';
import Gdk from 'gi://Gdk?version=4.0';

const PHOTO = '/usr/share/backgrounds/Resolute_Raccoon_Wallpaper_Light_3840x2160.png';
const SAMPLE = 'The quick brown fox jumps over the lazy dog 0123456789';

const app = new Gtk.Application({application_id: 'dev.scrollzoom.TestPage'});
app.connect('activate', () => {
    const css = new Gtk.CssProvider();
    css.load_from_string(`
        window { background: white; }
        .dark { background: #1e1e1e; color: #e8e8e8; padding: 6px; }
        .blue { color: #1a5fb4; }
        .red { color: #c01c28; }
    `);
    Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), css,
        Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION);

    const box = new Gtk.Box({orientation: Gtk.Orientation.VERTICAL, spacing: 4,
        margin_start: 12, margin_top: 12, margin_end: 12});
    for (const [size, weight, family] of [
        [8, 400, 'Ubuntu Sans'], [9, 400, 'Ubuntu Sans'], [11, 400, 'Ubuntu Sans'],
        [11, 700, 'Ubuntu Sans'], [13, 400, 'DejaVu Serif'], [16, 400, 'Ubuntu Sans'],
        [24, 400, 'Ubuntu Sans'], [10, 400, 'DejaVu Sans Mono'],
    ]) {
        box.append(new Gtk.Label({
            xalign: 0,
            use_markup: true,
            label: `<span font_family="${family}" size="${size * 1024}" weight="${weight}">` +
                `${size}pt ${SAMPLE}</span>`,
        }));
    }
    const dark = new Gtk.Label({xalign: 0, label: `Light on dark: ${SAMPLE}`, css_classes: ['dark']});
    box.append(dark);
    box.append(new Gtk.Label({xalign: 0, label: `Blue link text ${SAMPLE}`, css_classes: ['blue']}));
    box.append(new Gtk.Label({xalign: 0, label: `Red warning text ${SAMPLE}`, css_classes: ['red']}));

    const row = new Gtk.Box({spacing: 12});
    const lines = new Gtk.DrawingArea({content_width: 260, content_height: 200});
    lines.set_draw_func((_area, cr, w, h) => {
        cr.setSourceRGB(1, 1, 1);
        cr.paint();
        cr.setSourceRGB(0, 0, 0);
        for (let i = 0; i < 12; i++) {
            cr.setLineWidth(i % 3 === 0 ? 2 : 1);
            cr.moveTo(10, 10 + i * 4);
            cr.lineTo(w - 10, 10 + i * 15);
            cr.stroke();
        }
        cr.arc(70, 150, 40, 0, 2 * Math.PI);
        cr.setLineWidth(1.5);
        cr.stroke();
        cr.arc(190, 150, 25, 0, 2 * Math.PI);
        cr.fill();
    });
    row.append(lines);
    const picture = Gtk.Picture.new_for_filename(PHOTO);
    picture.set_size_request(356, 200);
    picture.set_content_fit(Gtk.ContentFit.COVER);
    row.append(picture);
    box.append(row);

    const window = new Gtk.ApplicationWindow({
        application: app, title: 'Zoom test page',
        default_width: 1200, default_height: 760, child: box,
    });
    window.present();
});
app.run([]);
