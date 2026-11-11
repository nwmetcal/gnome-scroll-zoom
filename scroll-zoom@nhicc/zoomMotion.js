// SPDX-License-Identifier: GPL-2.0-or-later
// Zoom physics for Scroll Zoom. Pure logic with no shell imports, so it can
// be unit tested outside GNOME Shell.
//
// Everything works on the zoom "level", the natural log of the zoom factor
// (1x = 0, 2x = 0.69). In log space a wheel notch feels the same size at 2x as
// at 12x.
//
// - The view never jumps. It glides toward a target level, closing most of
//   the gap within a fraction of a second.
// - Mouse wheel notches move the target. Spinning the wheel fast moves it
//   further per notch, like macOS scroll acceleration.
// - Touchpad scrolling moves the target almost 1:1. Lifting the fingers
//   mid-swipe flings it: the zoom keeps going and coasts to a stop.

// Time constants, in seconds: how long the view takes to close ~63% of the
// gap to the target.
const WHEEL_GLIDE = 0.085;
const TOUCHPAD_GLIDE = 0.025;
const KEYBOARD_GLIDE = 0.11;
// How quickly a touchpad fling slows down.
const FLING_FRICTION = 0.33;
// Touchpad releases slower than this (levels per second) just stop.
const MIN_FLING_SPEED = 0.35;
const STOP_SPEED = 0.02;
// Wheel acceleration: below ACCEL_START notches per second a notch is one
// step; faster spinning ramps up to ACCEL_MAX steps per notch.
const ACCEL_START = 8;
const ACCEL_RANGE = 16;
const ACCEL_MAX = 2;
const RATE_SMOOTHING = 0.12;
// Gaps smaller than this count as arrived.
const SETTLE_EPSILON = 1e-4;
// Ignore frame gaps longer than this so a stalled frame doesn't lurch.
const MAX_FRAME_TIME = 0.05;

export class ZoomMotion {
    constructor(maxLevel = Math.log(20)) {
        this.maxLevel = maxLevel;
        this.reset(0);
    }

    // Jump straight to a level, e.g. one set outside this class.
    reset(level, now = 0) {
        this.level = level;
        this.target = level;
        this.velocity = 0;
        this._glide = WHEEL_GLIDE;
        this._lastStep = now;
        this._lastWheel = -Infinity;
        this._lastNotches = 0;
        this._wheelRate = 0;
        this._lastTouch = -Infinity;
        this._touchVelocity = 0;
    }

    get settled() {
        return this.velocity === 0 && Math.abs(this.target - this.level) < SETTLE_EPSILON;
    }

    // `notches` is signed (positive zooms in), `stepLevel` the level change
    // of one unaccelerated notch.
    wheel(notches, stepLevel, now) {
        this._wake(now);
        const reversed = Math.sign(notches) !== Math.sign(this._lastNotches);
        const gap = now - this._lastWheel;
        this._lastWheel = now;
        this._lastNotches = notches;
        if (gap > 0.3 || reversed) {
            this._wheelRate = 0;
        } else if (gap > 0) {
            const rate = Math.abs(notches) / Math.max(gap, 0.004);
            this._wheelRate += (rate - this._wheelRate) * (1 - Math.exp(-gap / RATE_SMOOTHING));
        }
        const accel = 1 + Math.min(ACCEL_MAX - 1,
            Math.max(0, (this._wheelRate - ACCEL_START) / ACCEL_RANGE * (ACCEL_MAX - 1)));

        // Reversing direction cancels leftover travel instead of fighting it.
        if (reversed && Math.sign(notches) !== Math.sign(this.target - this.level))
            this.target = this.level;

        this.velocity = 0;
        this._glide = WHEEL_GLIDE;
        this._moveTarget(notches * stepLevel * accel);
    }

    // A touchpad scroll moved the target by `deltaLevel`.
    touch(deltaLevel, now) {
        this._wake(now);
        const gap = now - this._lastTouch;
        this._lastTouch = now;
        if (gap > 0 && gap < 0.1) {
            const speed = deltaLevel / gap;
            this._touchVelocity += (speed - this._touchVelocity) * (1 - Math.exp(-gap / 0.05));
        } else {
            this._touchVelocity = 0;
        }
        this.velocity = 0;
        this._glide = TOUCHPAD_GLIDE;
        this._moveTarget(deltaLevel);
    }

    // Fingers lifted off the touchpad: fling if they were still moving.
    release(now) {
        if (now - this._lastTouch < 0.08 && Math.abs(this._touchVelocity) > MIN_FLING_SPEED) {
            this._wake(now);
            this.velocity = this._touchVelocity;
        }
        this._touchVelocity = 0;
    }

    // Glide to an exact level, e.g. for keyboard zoom.
    glideTo(level, now) {
        this._wake(now);
        this.velocity = 0;
        this._glide = KEYBOARD_GLIDE;
        this.target = this._clamp(level);
    }

    // Advance to time `now` (seconds) and return the level to show.
    step(now) {
        const dt = Math.min(Math.max(now - this._lastStep, 0), MAX_FRAME_TIME);
        this._lastStep = now;

        if (this.velocity !== 0) {
            this._moveTarget(this.velocity * dt);
            this.velocity *= Math.exp(-dt / FLING_FRICTION);
            if (Math.abs(this.velocity) < STOP_SPEED)
                this.velocity = 0;
        }

        this.level += (this.target - this.level) * (1 - Math.exp(-dt / this._glide));
        if (this.settled)
            this.level = this.target;
        return this.level;
    }

    _wake(now) {
        if (this.settled)
            this._lastStep = now;
    }

    _moveTarget(delta) {
        const target = this.target + delta;
        this.target = this._clamp(target);
        if (this.target !== target)
            this.velocity = 0;
    }

    _clamp(level) {
        return Math.min(Math.max(level, 0), this.maxLevel);
    }
}
