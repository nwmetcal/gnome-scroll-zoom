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

import Atspi from 'gi://Atspi';
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

const MOUSE_PUSH = GDesktopEnums.MagnifierMouseTrackingMode.PUSH;

// Room following leaves around what it brings into view, in pixels of the unzoomed screen:
// the room GNOME's own push leaves for the pointer. Less when the view has less to spare.
const FOLLOW_MARGIN_PX = 24;
// How long the pointer must rest before following moves the view, as GNOME's zoom waits.
const POINTER_REST_MS = 1000;

const now = () => GLib.get_monotonic_time() / 1e6;

// Where a view `size` long, starting at `start`, must start to show `low` to `low + extent`,
// moving no further than that. Something already in view leaves the view still, so a text
// cursor moving within it never moves it; something brought in gets what room the view can
// spare; something longer than the view keeps the view within it, so focus going into a text
// area that already fills the view leaves the lines being read where they are.
function shownStart(start, size, low, extent) {
    if (extent >= size)
        return Math.min(Math.max(start, low), low + extent - size);
    if (low >= start && low + extent <= start + size)
        return start;
    const margin = Math.min(FOLLOW_MARGIN_PX, (size - extent) / 2);
    return low < start ? low - margin : low + extent + margin - size;
}

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
        this._held = null;
        this._restId = 0;
        this._pushAnchor = null;
        this._pointerMovedAtS = -Infinity;

        this._motion = new ZoomMotion(Math.log(this._settings.get_double('max-zoom')));
        this._timeline = new Clutter.Timeline({actor: global.stage, duration: 1000, repeat_count: -1});
        this._timeline.connectObject('new-frame', () => this._onFrame(), this);

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
            'position-invalidated', () => this._onPointerMoved(), this);
    }

    disable() {
        Main.wm.removeKeybinding('toggle-smooth-images');
        global.stage.disconnect(this._capturedEventId);
        global.backend.get_cursor_tracker().disconnectObject(this);
        this._settings.disconnectObject(this);
        if (this._panLater)
            global.compositor.get_laters().remove(this._panLater);

        this._timeline.stop();
        this._timeline.disconnectObject(this);
        this._timeline = null;
        // Mid-glide, finish where the zoom was heading.
        if (!this._motion.settled && Main.magnifier?.isActive()) {
            if (this._motion.target <= OFF_LEVEL)
                this._turnOff();
            else
                this._applyLevel(this._motion.target);
        }

        if (this._region) {
            this._dropHeldFollow();
            Main.magnifier.disconnect(this._activeChangedId);
            delete this._region.setMagFactor;
            const tracker = this._region._focusCaretTracker;
            tracker.disconnect(this._focusChangedId);
            tracker.disconnect(this._caretMovedId);
            delete this._region._centerFromFocusPosition;
            delete this._region._centerFromCaretPosition;
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
            // GNOME echoes the level Scroll Zoom saved, to two decimal places. Any other
            // level moves the pointer GNOME's way, so the next zoom starts from where it is.
            if (Math.abs(xMagFactor - this.getMagFactor()[0]) > 0.01)
                extension._pushAnchor = null;
            extension._syncMotion();
            extension._followPointer = false;
            extension._motion.glideTo(Math.log(xMagFactor), now());
            extension._run();
        };
    }

    // GNOME's magnifier sets its zoom region's following of focus and the text cursor from its
    // own settings, when the shell starts and on every change to them. Answer each of those
    // calls with Scroll Zoom's own switch instead, so a change to GNOME's settings never brings
    // following back. A switch that is on keeps GNOME listening for focus and the text cursor,
    // but Scroll Zoom places the view: GNOME places it from the middle of what moved, which
    // leaves most of a control above or left of the view out of it, and skips a move to where
    // it saw the last one, so focus going back to a control it showed before goes unshown.
    _routeFollowing() {
        const extension = this;
        const region = this._region;
        for (const [key, method, , modes] of FOLLOWING) {
            const set = region[method];
            region[method] = function (_gnomeMode) {
                set.call(this, extension._settings.get_boolean(key) ? modes.PUSH : modes.NONE);
            };
        }
        region._centerFromFocusPosition = () => {};
        region._centerFromCaretPosition = () => {};
        const tracker = region._focusCaretTracker;
        this._focusChangedId = tracker.connect('focus-changed',
            (_tracker, event) => this._onFocusChanged(event));
        this._caretMovedId = tracker.connect('caret-moved',
            (_tracker, event) => this._onCaretMoved(event));
        // A follow GNOME was holding back for the pointer to rest, from before Scroll Zoom came
        // on, is not one the switches asked for.
        region._xDelayed = null;
        region._yDelayed = null;
        this._syncFollowing();
    }

    _syncFollowing() {
        if (!this._region)
            return;
        for (const [, method] of FOLLOWING)
            this._region[method]();
        this._dropHeldFollow();
    }

    _onFocusChanged(event) {
        // GNOME sends focus being lost too; only focus arriving is followed.
        if (!this._settings.get_boolean('follow-focus') || event.detail1 !== 1)
            return;
        const component = event.source.get_component_iface();
        if (component) {
            this._bringIntoView(event.source,
                () => component.get_extents(Atspi.CoordType.WINDOW));
        }
    }

    _onCaretMoved(event) {
        if (!this._settings.get_boolean('follow-text-cursor'))
            return;
        const text = event.source.get_text_iface();
        if (text) {
            this._bringIntoView(text, () =>
                text.get_character_extents(text.get_caret_offset(), Atspi.CoordType.WINDOW));
        }
    }

    // While the pointer has moved in the last second, a hand on the mouse wins, as in GNOME's
    // own zoom. Hold only what moved last, and look up where it is when the pointer rests, so
    // what lands is worked out from the view and the focus as they are then: nothing, once
    // another window has focus or its own has closed.
    _bringIntoView(accessible, readExtents) {
        if (!this._region.isActive())
            return;
        const box = this._placeOf(accessible, readExtents);
        if (!box)
            return;
        const restLeftMs = POINTER_REST_MS - (now() - this._pointerMovedAtS) * 1000;
        if (restLeftMs > 0) {
            this._held = {accessible, readExtents, window: global.display.focus_window};
            this._waitForRest(restLeftMs);
            return;
        }
        this._dropHeldFollow();
        this._show(box);
    }

    // Where what moved is on the screen. GNOME finds no place for what is not in the focused
    // window, and some text cursors have a place of no size.
    _placeOf(accessible, readExtents) {
        const box = this._region._convertExtentsToScreenSpace(accessible, readExtents());
        return !box || (box.width === 0 && box.height === 0) ? null : box;
    }

    _onPointerMoved() {
        this._pointerMovedAtS = now();
        // Where the pointer is drawn changes with it, so the next zoom starts from there.
        this._pushAnchor = null;
        if (this._held)
            this._waitForRest(POINTER_REST_MS);
        this._queuePan();
    }

    _waitForRest(delayMs) {
        if (this._restId)
            GLib.source_remove(this._restId);
        this._restId = GLib.timeout_add(GLib.PRIORITY_DEFAULT, Math.ceil(delayMs), () => {
            this._restId = 0;
            const held = this._held;
            this._held = null;
            // Looking it up again in a window that has closed would ask an app that is gone.
            if (held && global.display.focus_window === held.window) {
                const box = this._placeOf(held.accessible, held.readExtents);
                if (box)
                    this._show(box);
            }
            return GLib.SOURCE_REMOVE;
        });
    }

    _dropHeldFollow() {
        this._held = null;
        if (this._restId) {
            GLib.source_remove(this._restId);
            this._restId = 0;
        }
    }

    // The least move, so what was in view stays close by.
    _show(box) {
        const region = this._region;
        if (!region.isActive())
            return;
        const [x, y, width, height] = region.getROI();
        const left = shownStart(x, width, box.x, box.width);
        const top = shownStart(y, height, box.y, box.height);
        if (left !== x || top !== y)
            region.scrollContentsTo(left + width / 2, top + height / 2);
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
                const centre = this._followPointer
                    ? this._pushCentre(factor, !Main.magnifier.isActive()) : null;
                region._changeROI({
                    xMagFactor: factor,
                    yMagFactor: factor,
                    ...centre,
                    // A glide the wheel or touchpad started stays on the pointer all the
                    // way. GNOME's own following lasts a second after zoom comes on, so a
                    // slow spin would otherwise settle where the view was then. A level that
                    // comes in through setMagFactor, from keyboard zoom, the Settings slider,
                    // or GNOME handing back this extension's own save, keeps GNOME's way,
                    // which hands over to focus tracking. Under GNOME's push the centre places
                    // the view, and GNOME's push must not move it again.
                    redoCursorTracking: !centre && (this._followPointer || region._followingCursor),
                    animate: false,
                });
            } else {
                region.setMagFactor(factor, factor);
            }
        } finally {
            this._applying = false;
        }
    }

    // Each time zoom comes on, by the wheel or by GNOME's toggle, place the view for the
    // pointer: under push, so the pointer stays where it is drawn, and otherwise as GNOME's
    // following places it. GNOME's magnifier skips that when the pointer has not moved since
    // zoom was last on, so the view would come on around wherever it was then.
    // When Super+Alt+8 or Settings turned zoom on or off, also stop any glide.
    _onActiveChanged(active) {
        if (active) {
            const centre = this._pushCentre(this._region.getMagFactor()[0], true);
            if (centre)
                this._region._changeROI(centre);
            else
                this._region.scrollToMousePos();
        }
        if (this._settingActive)
            return;
        this._timeline.stop();
        this._motion.reset(active ? Math.log(this._region.getMagFactor()[0]) : 0, now());
    }

    // Under GNOME's push, zooming keeps the pointer where it is drawn, so neither it nor what
    // is under it jumps. GNOME's own push zooms around the view's middle and then pushes the
    // pointer back into view, toward an edge. The pointer stays where it was drawn when it
    // was last put there, by moving or as zoom came on, as near as keeps the whole of its
    // image, which GNOME's push holds in the view, within the view, so the view stays still
    // as the pointer then moves. That place is kept until the pointer moves, not until a
    // glide ends, so where the pointer is drawn depends only on it and the zoom, and a zoom
    // that goes in deep and turns back brings the pointer back however it got there. The view
    // is GNOME's, on the whole screen or half of it, and what it shows stays within the
    // screen. `fromOff` is for zoom coming on, when the pointer is drawn where it is. Under
    // GNOME's other following, no centre.
    _pushCentre(factor, fromOff) {
        const region = this._region;
        if (this._magSettings.get_enum('mouse-tracking') !== MOUSE_PUSH ||
            typeof region._changeROI !== 'function' || !region._mouseSourceActor)
            return null;
        const pointer = global.get_pointer();
        const view = [region._viewPortX, region._viewPortY,
            region._viewPortWidth, region._viewPortHeight];
        if (fromOff || !this._pushAnchor) {
            const roi = region.getROI();
            const was = region.getMagFactor()[0];
            this._pushAnchor = [0, 1].map(axis => fromOff
                ? pointer[axis] : view[axis] + (pointer[axis] - roi[axis]) * was);
        }
        const image = region._mouseSourceActor.get_size();
        const screen = [global.screen_width, global.screen_height];
        const [xCenter, yCenter] = [0, 1].map(axis => {
            const [origin, size] = [view[axis], view[axis + 2]];
            const kept = Math.min(Math.max(this._pushAnchor[axis], origin),
                origin + size - image[axis] * factor);
            // GNOME's Extend Outside Screen Edges lets the view past the right and bottom
            // edges, as far as GNOME's push takes it to show the pointer's whole image.
            const past = region._clampScrollingAtEdges
                ? 0 : Math.max(pointer[axis] + image[axis] - screen[axis], 0);
            const start = Math.min(Math.max(pointer[axis] - (kept - origin) / factor, 0),
                screen[axis] - size / factor + past);
            return start + size / factor / 2;
        });
        return {xCenter, yCenter};
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
