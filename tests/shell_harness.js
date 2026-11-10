// SPDX-License-Identifier: GPL-2.0-or-later
// Test helpers, loaded into the private test shell (dev/test-shell.sh) by
// tests/shell.py. Input goes through virtual devices, so it takes the same path
// through the compositor as a real keyboard, mouse, and touchpad. What the
// tests observe is GNOME's own: the magnifier's state, the frames drawn, and
// screenshots.
//
// Evaluated by the shell's Eval method, where `Main` and `imports.gi` are in
// scope.
(() => {
    const {Clutter, GLib, Pango, PangoCairo, St} = imports.gi;
    const UUID = 'scroll-zoom@nhicc';
    const seat = global.stage.get_context().get_backend().get_default_seat();
    const microseconds = () => GLib.get_monotonic_time();

    const KEYS = {
        super: Clutter.KEY_Super_L,
        alt: Clutter.KEY_Alt_L,
        ctrl: Clutter.KEY_Control_L,
        shift: Clutter.KEY_Shift_L,
        backslash: Clutter.KEY_backslash,
        return: Clutter.KEY_Return,
        tab: Clutter.KEY_Tab,
    };

    // Where the test pattern sits on screen, and what is in it, in stage pixels
    // from its top-left corner.
    const PATTERN = {
        x: 600, y: 300, width: 120, height: 130,
        text: {x: 8, y: 4, width: 104, height: 44},
        fullStem: 12, splitStem: 15.5, stems: {y: 56, height: 40},
        gradient: {x: 30, y: 56, width: 64, height: 40},
        serif: {x: 8, y: 104, width: 104, height: 22},
        square: {x: 20.3, y: 60.6, width: 6, height: 6},
        ell: {x: 19.3, y: 72.6, width: 8, height: 10, stroke: 2},
        light: {x: 0, y: 150, width: 120, height: 80},
        lightText: {x: 8, y: 154, width: 104, height: 44},
        lightSerif: {x: 8, y: 202, width: 104, height: 22},
    };

    const extension = () => Main.extensionManager.lookup(UUID);
    const region = () => Main.magnifier.getZoomRegions()[0];

    globalThis.scrollZoomTest = {
        PATTERN,
        keyboard: seat.create_virtual_device(Clutter.InputDeviceType.KEYBOARD_DEVICE),
        pointer: seat.create_virtual_device(Clutter.InputDeviceType.POINTER_DEVICE),
        busy: false,
        frames: [],
        _paintId: 0,

        // Run [delay ms, action, ...arguments] steps one after another, each
        // after its delay, so a test can say "a notch every 120 ms".
        run(steps) {
            this.busy = true;
            let index = 0;
            const next = () => {
                if (index >= steps.length) {
                    this.busy = false;
                    return;
                }
                const [delay, action, ...args] = steps[index++];
                GLib.timeout_add(GLib.PRIORITY_DEFAULT, Math.max(delay, 1), () => {
                    this[action](...args);
                    next();
                    return GLib.SOURCE_REMOVE;
                });
            };
            next();
            return true;
        },

        press(key) {
            this.keyboard.notify_keyval(microseconds(), KEYS[key], Clutter.KeyState.PRESSED);
        },

        release(key) {
            this.keyboard.notify_keyval(microseconds(), KEYS[key], Clutter.KeyState.RELEASED);
        },

        // One click of a mouse wheel; positive is away from you (up).
        notch(direction) {
            this.pointer.notify_discrete_scroll(microseconds(),
                direction > 0 ? Clutter.ScrollDirection.UP : Clutter.ScrollDirection.DOWN,
                Clutter.ScrollSource.WHEEL);
        },

        // Two fingers on a touchpad move `dy` pixels (negative is up).
        swipe(dy) {
            this.pointer.notify_scroll_continuous(microseconds(), 0, dy,
                Clutter.ScrollSource.FINGER, Clutter.ScrollFinishFlags.NONE);
        },

        lift() {
            this.pointer.notify_scroll_continuous(microseconds(), 0, 0,
                Clutter.ScrollSource.FINGER, Clutter.ScrollFinishFlags.VERTICAL);
        },

        moveTo(x, y) {
            this.pointer.notify_absolute_motion(microseconds(), x, y);
        },

        record() {
            this.frames = [];
            if (this._paintId)
                global.stage.disconnect(this._paintId);
            this._paintId = global.stage.connect('after-paint', () => {
                const [x, y] = global.get_pointer();
                this.frames.push({
                    ms: microseconds() / 1000,
                    on: Main.magnifier.isActive(),
                    zoom: region().getMagFactor()[0],
                    roi: region().getROI(),
                    pointer: [x, y],
                });
            });
            return true;
        },

        stopRecording() {
            if (this._paintId)
                global.stage.disconnect(this._paintId);
            this._paintId = 0;
            return this.frames;
        },

        state() {
            return {
                on: Main.magnifier.isActive(),
                zoom: region().getMagFactor()[0],
                overview: Main.overview.visible,
                extension: extension()?.state ?? null,
                error: extension()?.error || null,
                pointer: global.get_pointer().slice(0, 2),
            };
        },

        settings() {
            return extension().stateObj.getSettings();
        },

        // A switch of the extension's own, as a run step, so it can change between timed moves.
        setBoolean(key, value) {
            this.settings().set_boolean(key, value);
        },

        disableExtension() {
            Main.extensionManager.disableExtension(UUID);
        },

        enableExtension() {
            Main.extensionManager.enableExtension(UUID);
        },

        windows() {
            return global.get_window_actors().map(actor => actor.meta_window.get_title());
        },

        closeWindows() {
            for (const actor of global.get_window_actors())
                actor.meta_window.delete(global.get_current_time());
            return true;
        },

        // How X11 apps reach the test shell's Xwayland: its display, and the authority file
        // that lets them in.
        xDisplay() {
            return {display: GLib.getenv('DISPLAY'), authority: GLib.getenv('XAUTHORITY')};
        },

        hidePattern() {
            this._pattern?.hide();
            return true;
        },

        // A known starting point: zoom off, GNOME's level at 2x, the view
        // centred on the pointer, GNOME's following of focus and the text cursor at its
        // defaults, and the extension at its defaults.
        reset() {
            if (this._paintId)
                this.stopRecording();
            const settings = this.settings();
            for (const key of settings.settings_schema.list_keys())
                settings.reset(key);
            const gio = imports.gi.Gio;
            const magnifier = new gio.Settings({schema_id: 'org.gnome.desktop.a11y.magnifier'});
            magnifier.set_string('mouse-tracking', 'centered');
            magnifier.reset('focus-tracking');
            magnifier.reset('caret-tracking');
            new gio.Settings({schema_id: 'org.gnome.desktop.a11y.applications'})
                .set_boolean('screen-magnifier-enabled', false);
            Main.magnifier.setActive(false);
            // GNOME's magnifier remembers where it last saw the pointer and skips re-centring
            // when it comes on with the pointer still there; start each scenario as a fresh
            // session does, so none inherits the last one's pointer.
            Main.magnifier.xMouse = undefined;
            Main.magnifier.yMouse = undefined;
            // Its zoom region skips a focus change or a text cursor move to where it saw the
            // last one, so clear those as a fresh session starts.
            Object.assign(region(), {_xFocus: 0, _yFocus: 0, _xCaret: 0, _yCaret: 0});
            magnifier.set_double('mag-factor', 2.0);
            Main.overview.hide();
            for (const key of Object.keys(KEYS))
                this.release(key);
            return true;
        },

        // Turn zoom on at an exact level, the way GNOME's toggle does.
        zoomTo(level) {
            const gio = imports.gi.Gio;
            new gio.Settings({schema_id: 'org.gnome.desktop.a11y.magnifier'})
                .set_double('mag-factor', level);
            new gio.Settings({schema_id: 'org.gnome.desktop.a11y.applications'})
                .set_boolean('screen-magnifier-enabled', true);
            return true;
        },

        showPattern() {
            if (this._pattern) {
                this._pattern.show();
                return true;
            }
            const group = new St.Widget({x: PATTERN.x, y: PATTERN.y});
            const area = new St.DrawingArea({width: PATTERN.width, height: PATTERN.height});
            area.connect('repaint', () => {
                const cr = area.get_context();
                cr.setSourceRGB(1, 1, 1);
                cr.paint();
                cr.setSourceRGB(0.1, 0.1, 0.1);
                const layout = PangoCairo.create_layout(cr);
                layout.set_font_description(Pango.FontDescription.from_string('Ubuntu Sans 11px'));
                layout.set_width(PATTERN.text.width * Pango.SCALE);
                layout.set_text('The quick brown fox jumps over the lazy dog', -1);
                cr.moveTo(PATTERN.text.x, PATTERN.text.y);
                PangoCairo.show_layout(cr, layout);
                // A one-pixel stem on the pixel grid, and one that falls half
                // across each of two columns, three pixels to its right.
                cr.rectangle(PATTERN.fullStem, PATTERN.stems.y, 1, PATTERN.stems.height);
                cr.rectangle(PATTERN.splitStem, PATTERN.stems.y, 1, PATTERN.stems.height);
                // A square whose sides all fall between pixels, as a letter's mostly do.
                const {square, ell} = PATTERN;
                cr.rectangle(square.x, square.y, square.width, square.height);
                // An L, so it has an inside corner too, set off the pixel grid as well.
                cr.rectangle(ell.x, ell.y, ell.stroke, ell.height);
                cr.rectangle(ell.x, ell.y + ell.height - ell.stroke, ell.width, ell.stroke);
                cr.fill();
                // Serif capitals, with upright strokes the font draws thick, and bars and
                // serifs it draws thin.
                const serif = PangoCairo.create_layout(cr);
                serif.set_font_description(
                    Pango.FontDescription.from_string('Liberation Serif 15px'));
                serif.set_text('THE HILL', -1);
                cr.moveTo(PATTERN.serif.x, PATTERN.serif.y);
                PangoCairo.show_layout(cr, serif);
                const {x, y, width, height} = PATTERN.gradient;
                for (let i = 0; i < width; i++) {
                    const v = 1 - i / (width - 1);
                    cr.setSourceRGB(v, v, v);
                    cr.rectangle(x + i, y, 1, height);
                    cr.fill();
                }
                cr.$dispose();
            });
            // The same text and serif capitals in light ink on a dark ground, as a dark
            // theme draws them, below the pattern and out of view where it is zoomed over.
            const {light, lightText, lightSerif} = PATTERN;
            const dark = new St.DrawingArea({
                x: light.x, y: light.y, width: light.width, height: light.height,
            });
            dark.connect('repaint', () => {
                const cr = dark.get_context();
                cr.setSourceRGB(0.1, 0.1, 0.1);
                cr.paint();
                cr.setSourceRGB(1, 1, 1);
                const layout = PangoCairo.create_layout(cr);
                layout.set_font_description(Pango.FontDescription.from_string('Ubuntu Sans 11px'));
                layout.set_width(lightText.width * Pango.SCALE);
                layout.set_text('The quick brown fox jumps over the lazy dog', -1);
                cr.moveTo(lightText.x - light.x, lightText.y - light.y);
                PangoCairo.show_layout(cr, layout);
                const serif = PangoCairo.create_layout(cr);
                serif.set_font_description(
                    Pango.FontDescription.from_string('Liberation Serif 15px'));
                serif.set_text('THE HILL', -1);
                cr.moveTo(lightSerif.x - light.x, lightSerif.y - light.y);
                PangoCairo.show_layout(cr, serif);
                cr.$dispose();
            });
            group.add_child(area);
            group.add_child(dark);
            Main.uiGroup.add_child(group);
            this._pattern = group;
            return true;
        },
    };
    return true;
})();
