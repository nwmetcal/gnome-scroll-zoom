// SPDX-License-Identifier: GPL-2.0-or-later
// Scroll Zoom: hold Super and scroll to zoom the whole screen around the
// pointer, like macOS's "Use scroll gesture with modifier keys to zoom".
//
// It drives GNOME's own magnifier (Main.magnifier), so the Super+Alt+8 toggle,
// Settings > Accessibility > Zoom and pointer tracking all keep working. On
// top of that it:
// - glides between zoom levels instead of jumping (zoomMotion.js),
// - moves the zoomed view on every pointer movement, in step with the
//   display, instead of on GNOME's 60 Hz timer,
// - redraws zoomed text with clean edges instead of blur (smoothing.js),
// - leaves the view with the pointer when keyboard focus or a text cursor
//   moves, unless its own settings say to follow them.
//
// Why the keys always include Super: on Wayland, mutter sends scroll events
// straight to the app under the pointer unless the window-drag modifier
// (org.gnome.desktop.wm.preferences mouse-button-modifier, Super by default)
// is held. Only then do they reach the shell, where this extension sees them.

import Clutter from 'gi://Clutter';
import GDesktopEnums from 'gi://GDesktopEnums';
import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import Meta from 'gi://Meta';
import Shell from 'gi://Shell';

import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';

import {Mode, RegionSmoothing} from './smoothing.js';
import {ZoomMotion} from './zoomMotion.js';

const A11Y_APPS_SCHEMA = 'org.gnome.desktop.a11y.applications';
const MAGNIFIER_ENABLED_KEY = 'screen-magnifier-enabled';
const MAGNIFIER_SCHEMA = 'org.gnome.desktop.a11y.magnifier';
const MAG_FACTOR_KEY = 'mag-factor';

// Gliding out to within 1% of 1x turns the magnifier off.
const OFF_LEVEL = Math.log(1.01);
// Levels below this look unzoomed, so they aren't kept as "your zoom level"
// for Super+Alt+8 to restore.
const MIN_REMEMBERED_ZOOM = 1.25;
const DEFAULT_REMEMBERED_ZOOM = 2.0;
// Save the level to GNOME's settings once zooming has stopped this long.
const SAVE_DELAY_MS = 400;
// Mouse wheels send a smooth scroll event plus a discrete copy. After a smooth
// event, ignore discrete ones for this long (seconds) so each notch counts once.
const SMOOTH_DEDUP = 1.0;

const KEY_MASKS = {
    super: Clutter.ModifierType.SUPER_MASK | Clutter.ModifierType.MOD4_MASK,
    alt: Clutter.ModifierType.MOD1_MASK,
    ctrl: Clutter.ModifierType.CONTROL_MASK,
    shift: Clutter.ModifierType.SHIFT_MASK,
};

const COMBOS = {
    'super': ['super'],
    'super-alt': ['super', 'alt'],
    'super-ctrl': ['super', 'ctrl'],
    'super-shift': ['super', 'shift'],
};

const STYLE_MODES = {
    text: Mode.TEXT,
    soft: Mode.SOFT,
    standard: null, // GNOME's own rendering, no shader
};

// Each switch stands in for one of GNOME's own following settings, through the zoom region
// setter GNOME calls with it, so that setting can be handed back when the extension is off.
const FOLLOWING = [
    ['follow-focus', 'setFocusTrackingMode', 'focus-tracking',
        GDesktopEnums.MagnifierFocusTrackingMode],
    ['follow-text-cursor', 'setCaretTrackingMode', 'caret-tracking',
        GDesktopEnums.MagnifierCaretTrackingMode],
];

const now = () => GLib.get_monotonic_time() / 1e6;

export default class ScrollZoomExtension extends Extension {
    enable() {
        this._settings = this.getSettings();
        this._a11ySettings = new Gio.Settings({schema_id: A11Y_APPS_SCHEMA});
        this._magSettings = new Gio.Settings({schema_id: MAGNIFIER_SCHEMA});
        this._lastSmoothTime = -Infinity;
        this._saveId = 0;
        this._panLater = 0;
        this._applying = false;
        this._followPointer = false;
        this._settingActive = false;
        this._smoothing = null;

        this._motion = new ZoomMotion(Math.log(this._settings.get_double('max-zoom')));
        this._timeline = new Clutter.Timeline({actor: global.stage, duration: 1000, repeat_count: -1});
        this._timeline.connect('new-frame', () => this._onFrame());

        this._region = Main.magnifier?.getZoomRegions()[0] ?? null;
        if (this._region) {
            this._routeMagFactorChanges();
            this._routeFollowing();
            this._activeChangedId = Main.magnifier.connect('active-changed',
                (_magnifier, active) => this._onActiveChanged(active));
        }

        this._settings.connectObject(
            'changed::max-zoom', () => {
                this._motion.maxLevel = Math.log(this._settings.get_double('max-zoom'));
            },
            'changed::smooth-images', () => this._syncSmoothing(),
            'changed::smoothing-style', () => this._syncSmoothing(),
            'changed::edge-width', () => this._syncSmoothing(),
            'changed::edge-position', () => this._syncSmoothing(),
            'changed::follow-focus', () => this._syncFollowing(),
            'changed::follow-text-cursor', () => this._syncFollowing(),
            this);
        this._syncSmoothing();

        Main.wm.addKeybinding('toggle-smooth-images', this._settings,
            Meta.KeyBindingFlags.NONE, Shell.ActionMode.ALL,
            () => this._settings.set_boolean('smooth-images',
                !this._settings.get_boolean('smooth-images')));

        this._capturedEventId = global.stage.connect('captured-event',
            (_stage, event) => this._onCapturedEvent(event));
        global.backend.get_cursor_tracker().connectObject(
            'position-invalidated', () => this._queuePan(), this);
    }

    disable() {
        Main.wm.removeKeybinding('toggle-smooth-images');
        global.stage.disconnect(this._capturedEventId);
        global.backend.get_cursor_tracker().disconnectObject(this);
        this._settings.disconnectObject(this);
        if (this._panLater)
            global.compositor.get_laters().remove(this._panLater);

        this._timeline.stop();
        this._timeline = null;
        // Mid-glide, finish where the zoom was heading.
        if (!this._motion.settled && Main.magnifier?.isActive()) {
            if (this._motion.target <= OFF_LEVEL)
                this._turnOff();
            else
                this._applyLevel(this._motion.target);
        }

        if (this._region) {
            Main.magnifier.disconnect(this._activeChangedId);
            delete this._region.setMagFactor;
            // With the routing gone, the zoom region would keep Scroll Zoom's last mode.
            for (const [, method, gnomeKey] of FOLLOWING) {
                delete this._region[method];
                this._region[method](this._magSettings.get_enum(gnomeKey));
            }
        }
        this._smoothing?.remove();
        this._smoothing = null;

        if (this._saveId) {
            this._cancelSave();
            this._saveZoom();
        }

        // The magnifier is left on: the shell disables extensions while the
        // screen is locked, and zoom shouldn't drop out when that happens.
        this._settings = null;
        this._a11ySettings = null;
        this._magSettings = null;
        this._motion = null;
        this._region = null;
    }

    _onCapturedEvent(event) {
        if (event.type() !== Clutter.EventType.SCROLL ||
            !this._modifiersMatch(event.get_state()))
            return Clutter.EVENT_PROPAGATE;

        this._onScroll(event);
        // Consume every scroll in the combo, including discrete duplicates.
        return Clutter.EVENT_STOP;
    }

    _modifiersMatch(state) {
        const wanted = COMBOS[this._settings.get_string('modifier')] ?? COMBOS.super;
        return Object.entries(KEY_MASKS).every(
            ([key, mask]) => ((state & mask) !== 0) === wanted.includes(key));
    }

    _onScroll(event) {
        const time = now();
        const sign = this._settings.get_boolean('invert-direction') ? -1 : 1;
        const stepLevel = Math.log(this._settings.get_double('zoom-step'));
        const direction = event.get_scroll_direction();

        if (direction === Clutter.ScrollDirection.SMOOTH) {
            this._lastSmoothTime = time;
            const [, dy] = event.get_scroll_delta();
            const notches = -dy * sign;
            if (event.get_scroll_source() === Clutter.ScrollSource.FINGER) {
                if (notches)
                    this._input(notches, () => this._motion.touch(notches * stepLevel, time));
                if (event.get_scroll_finish_flags() & Clutter.ScrollFinishFlags.VERTICAL) {
                    this._motion.release(time);
                    this._run();
                }
            } else if (notches) {
                this._input(notches, () => this._motion.wheel(notches, stepLevel, time));
            }
        } else if (direction === Clutter.ScrollDirection.UP ||
                   direction === Clutter.ScrollDirection.DOWN) {
            if (event.is_pointer_emulated() || time - this._lastSmoothTime < SMOOTH_DEDUP)
                return;
            const notches = (direction === Clutter.ScrollDirection.UP ? 1 : -1) * sign;
            this._input(notches, () => this._motion.wheel(notches, stepLevel, time));
        }
    }

    _input(direction, apply) {
        if (!this._region)
            return;
        // Zooming out with zoom off does nothing.
        if (direction < 0 && this._motion.settled && !Main.magnifier.isActive())
            return;
        this._syncMotion();
        this._followPointer = true;
        apply();
        this._run();
    }

    // GNOME's keyboard zoom (Super+Alt+= / -) and the Settings slider set the
    // zoom factor directly. Glide to it instead.
    _routeMagFactorChanges() {
        const extension = this;
        const setMagFactor = this._region.setMagFactor;
        this._region.setMagFactor = function (xMagFactor, yMagFactor) {
            if (!this.isActive() || extension._applying) {
                setMagFactor.call(this, xMagFactor, yMagFactor);
                return;
            }
            extension._syncMotion();
            extension._followPointer = false;
            extension._motion.glideTo(Math.log(xMagFactor), now());
            extension._run();
        };
    }

    // GNOME's magnifier sets its zoom region's following of focus and the text cursor from its
    // own settings, when the shell starts and on every change to them. Answer each of those
    // calls with Scroll Zoom's own switch instead, so a change to GNOME's settings never brings
    // following back. Push moves the view only as far as it takes to show what moved.
    _routeFollowing() {
        const extension = this;
        for (const [key, method, , modes] of FOLLOWING) {
            const set = this._region[method];
            this._region[method] = function (_gnomeMode) {
                set.call(this, extension._settings.get_boolean(key) ? modes.PUSH : modes.NONE);
            };
        }
        this._syncFollowing();
    }

    _syncFollowing() {
        if (!this._region)
            return;
        for (const [, method] of FOLLOWING)
            this._region[method]();
    }

    // Before a new movement, pick up the current zoom, which may have been
    // changed elsewhere since the last one.
    _syncMotion() {
        if (!this._motion.settled || this._timeline.is_playing())
            return;
        const level = Main.magnifier.isActive()
            ? Math.log(this._region.getMagFactor()[0]) : 0;
        this._motion.reset(level, now());
    }

    _run() {
        this._cancelSave();
        if (!this._timeline.is_playing())
            this._timeline.start();
    }

    _onFrame() {
        const level = this._motion.step(now());
        const target = this._motion.target;

        if (target <= OFF_LEVEL && level <= OFF_LEVEL) {
            this._timeline.stop();
            this._turnOff();
            return;
        }

        this._applyLevel(level);
        if (!Main.magnifier.isActive())
            this._setMagnifierActive(true);

        if (this._motion.settled) {
            this._timeline.stop();
            this._scheduleSave();
        }
    }

    _applyLevel(level) {
        const factor = Math.exp(level);
        const region = this._region;
        this._applying = true;
        try {
            // _changeROI is the magnifier's own internal update; unlike
            // setMagFactor it can skip the 100 ms ease, which would fight
            // the per-frame glide.
            if (typeof region._changeROI === 'function') {
                region._changeROI({
                    xMagFactor: factor,
                    yMagFactor: factor,
                    // A glide the wheel or touchpad started stays on the pointer all the
                    // way. GNOME's own following lasts a second after zoom comes on, so a
                    // slow spin would otherwise settle where the view was then. A level that
                    // comes in through setMagFactor, from keyboard zoom, the Settings slider,
                    // or GNOME handing back this extension's own save, keeps GNOME's way,
                    // which hands over to focus tracking.
                    redoCursorTracking: this._followPointer || region._followingCursor,
                    animate: false,
                });
            } else {
                region.setMagFactor(factor, factor);
            }
        } finally {
            this._applying = false;
        }
    }

    // Each time zoom comes on, by the wheel or by GNOME's toggle, centre the view on the
    // pointer. GNOME's magnifier skips that when the pointer has not moved since zoom was
    // last on, so the view would come on around wherever it was then.
    // When Super+Alt+8 or Settings turned zoom on or off, also stop any glide.
    _onActiveChanged(active) {
        if (active)
            this._region.scrollToMousePos();
        if (this._settingActive)
            return;
        this._timeline.stop();
        this._motion.reset(active ? Math.log(this._region.getMagFactor()[0]) : 0, now());
    }

    _turnOff() {
        this._cancelSave();
        this._motion.reset(0, now());
        this._setMagnifierActive(false);

        // Leave the magnifier set to the last level you settled on, so
        // Super+Alt+8 brings that back rather than an unzoomed 1x.
        let level = this._magSettings.get_double(MAG_FACTOR_KEY);
        if (level < MIN_REMEMBERED_ZOOM) {
            level = DEFAULT_REMEMBERED_ZOOM;
            this._magSettings.set_double(MAG_FACTOR_KEY, level);
        }
        this._region.setMagFactor(level, level);
    }

    _setMagnifierActive(active) {
        // The setting is what Super+Alt+8 and Settings read and toggle.
        // Calling setActive too applies it now instead of when the change
        // notification arrives (it does nothing if already in that state).
        this._settingActive = true;
        try {
            this._a11ySettings.set_boolean(MAGNIFIER_ENABLED_KEY, active);
            Main.magnifier.setActive(active);
        } finally {
            this._settingActive = false;
        }
    }

    // Move the zoomed view with the pointer once per frame, just before the
    // frame is drawn.
    _queuePan() {
        if (this._panLater || !Main.magnifier?.isActive())
            return;
        this._panLater = global.compositor.get_laters().add(Meta.LaterType.BEFORE_REDRAW, () => {
            this._panLater = 0;
            Main.magnifier?.scrollToMousePos();
            return GLib.SOURCE_REMOVE;
        });
    }

    _syncSmoothing() {
        const style = this._settings.get_string('smoothing-style');
        let mode = Mode.PIXELS;
        if (this._settings.get_boolean('smooth-images'))
            mode = style in STYLE_MODES ? STYLE_MODES[style] : Mode.TEXT;

        if (mode === null || !this._region) {
            this._smoothing?.remove();
            this._smoothing = null;
            return;
        }
        this._smoothing ??= new RegionSmoothing(this._region);
        this._smoothing.setStyle(mode,
            this._settings.get_double('edge-width'),
            this._settings.get_double('edge-position'));
    }

    _scheduleSave() {
        this._cancelSave();
        this._saveId = GLib.timeout_add(GLib.PRIORITY_DEFAULT, SAVE_DELAY_MS, () => {
            this._saveId = 0;
            this._saveZoom();
            return GLib.SOURCE_REMOVE;
        });
    }

    _cancelSave() {
        if (this._saveId) {
            GLib.source_remove(this._saveId);
            this._saveId = 0;
        }
    }

    _saveZoom() {
        const magnifier = Main.magnifier;
        if (!magnifier?.isActive())
            return;

        // The magnifier keeps two decimal places of this setting.
        const level = Math.round(this._region.getMagFactor()[0] * 100) / 100;
        const saved = this._magSettings.get_double(MAG_FACTOR_KEY);
        if (level >= MIN_REMEMBERED_ZOOM && Math.abs(level - saved) >= 0.005)
            this._magSettings.set_double(MAG_FACTOR_KEY, level);
    }
}
