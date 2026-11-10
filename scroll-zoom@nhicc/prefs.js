// SPDX-License-Identifier: GPL-2.0-or-later
import Adw from 'gi://Adw';
import Gio from 'gi://Gio';
import Gtk from 'gi://Gtk';

import {ExtensionPreferences} from 'resource:///org/gnome/Shell/Extensions/js/extensions/prefs.js';

const MODIFIERS = [
    ['super', 'Super'],
    ['super-alt', 'Super + Alt'],
    ['super-ctrl', 'Super + Ctrl'],
    ['super-shift', 'Super + Shift'],
];

const STYLES = [
    ['text', 'Sharp text and lines', 'Rebuilds crisp, smooth edges; photos stay soft'],
    ['soft', 'Soft', 'Smooth scaling everywhere'],
    ['standard', 'GNOME standard', 'GNOME\'s own scaling, slightly blurry'],
];

const SHORTCUTS = [
    ['magnifier', 'Turn zoom on or off'],
    ['magnifier-zoom-in', 'Zoom in'],
    ['magnifier-zoom-out', 'Zoom out'],
];

export default class ScrollZoomPreferences extends ExtensionPreferences {
    fillPreferencesWindow(window) {
        const settings = this.getSettings();
        window._settings = settings;

        const page = new Adw.PreferencesPage();
        window.add(page);

        const scrollGroup = new Adw.PreferencesGroup({
            title: 'Scroll to zoom',
            description: 'Hold the keys and scroll to zoom the screen around the pointer. ' +
                'Zoom all the way out to turn zoom off.',
        });
        page.add(scrollGroup);

        const modifierRow = new Adw.ComboRow({
            title: 'Keys to hold',
            subtitle: 'Always includes Super: GNOME sends other key + scroll combinations straight to apps',
            model: Gtk.StringList.new(MODIFIERS.map(([, label]) => label)),
        });
        const syncModifier = () => {
            const index = MODIFIERS.findIndex(([id]) => id === settings.get_string('modifier'));
            if (index >= 0 && modifierRow.selected !== index)
                modifierRow.selected = index;
        };
        syncModifier();
        settings.connect('changed::modifier', syncModifier);
        modifierRow.connect('notify::selected', () => {
            const [id] = MODIFIERS[modifierRow.selected];
            if (settings.get_string('modifier') !== id)
                settings.set_string('modifier', id);
        });
        scrollGroup.add(modifierRow);

        const stepRow = new Adw.SpinRow({
            title: 'Zoom speed',
            subtitle: 'Zoom per mouse-wheel notch (1.20 = 20% closer)',
            digits: 2,
            adjustment: new Gtk.Adjustment({lower: 1.05, upper: 2.0, step_increment: 0.05}),
        });
        settings.bind('zoom-step', stepRow, 'value', Gio.SettingsBindFlags.DEFAULT);
        scrollGroup.add(stepRow);

        const maxRow = new Adw.SpinRow({
            title: 'Maximum zoom',
            digits: 0,
            adjustment: new Gtk.Adjustment({lower: 2, upper: 32, step_increment: 1}),
        });
        settings.bind('max-zoom', maxRow, 'value', Gio.SettingsBindFlags.DEFAULT);
        scrollGroup.add(maxRow);

        const invertRow = new Adw.SwitchRow({
            title: 'Reverse direction',
            subtitle: 'Scroll down to zoom in',
        });
        settings.bind('invert-direction', invertRow, 'active', Gio.SettingsBindFlags.DEFAULT);
        scrollGroup.add(invertRow);

        const imageGroup = new Adw.PreferencesGroup({title: 'Zoomed image'});
        page.add(imageGroup);

        const smoothRow = new Adw.SwitchRow({
            title: 'Smooth images',
            subtitle: 'Off shows zoomed pixels as hard squares',
        });
        settings.bind('smooth-images', smoothRow, 'active', Gio.SettingsBindFlags.DEFAULT);
        smoothRow.add_suffix(new Gtk.ShortcutLabel({
            accelerator: settings.get_strv('toggle-smooth-images')[0] ?? '',
            disabled_text: '',
            valign: Gtk.Align.CENTER,
        }));
        imageGroup.add(smoothRow);

        const styleRow = new Adw.ComboRow({
            title: 'Smoothing style',
            model: Gtk.StringList.new(STYLES.map(([, label]) => label)),
        });
        const syncStyle = () => {
            const index = STYLES.findIndex(([id]) => id === settings.get_string('smoothing-style'));
            if (index >= 0 && styleRow.selected !== index)
                styleRow.selected = index;
            styleRow.subtitle = STYLES[styleRow.selected][2];
        };
        syncStyle();
        settings.connect('changed::smoothing-style', syncStyle);
        styleRow.connect('notify::selected', () => {
            const [id] = STYLES[styleRow.selected];
            if (settings.get_string('smoothing-style') !== id)
                settings.set_string('smoothing-style', id);
            styleRow.subtitle = STYLES[styleRow.selected][2];
        });
        settings.bind('smooth-images', styleRow, 'sensitive', Gio.SettingsBindFlags.GET);
        imageGroup.add(styleRow);

        const keysGroup = new Adw.PreferencesGroup({
            title: 'Keyboard shortcuts',
            description: 'These are GNOME\'s own zoom shortcuts. Change them in Settings > ' +
                'Keyboard > View and Customize Shortcuts > Accessibility.',
        });
        page.add(keysGroup);

        const mediaKeys = new Gio.Settings({schema_id: 'org.gnome.settings-daemon.plugins.media-keys'});
        window._mediaKeys = mediaKeys;
        for (const [key, title] of SHORTCUTS) {
            const row = new Adw.ActionRow({title});
            row.add_suffix(new Gtk.ShortcutLabel({
                accelerator: mediaKeys.get_strv(key)[0] ?? '',
                disabled_text: 'Not set',
                valign: Gtk.Align.CENTER,
            }));
            keysGroup.add(row);
        }
    }
}
