// SPDX-License-Identifier: GPL-2.0-or-later
// Plays a list of inputs into the zoom motion and prints the zoom level of
// every frame, as JSON, for tests/motion.py.
//
//   gjs -m tests/motion_driver.js '{"fps": 144, "seconds": 1, "start": 1, "inputs": [...]}'
//
// Each input is {"ms": time, "kind": "wheel" | "touch" | "lift" | "glide", "value": n}:
// wheel notches (positive zooms in), a touchpad move in zoom levels per the
// natural log, a lift of the fingers, or a glide to a zoom factor.
import System from 'system';

import {ZoomMotion} from '../scroll-zoom@nhicc/zoomMotion.js';

const plan = JSON.parse(ARGV[0]);
const fps = plan.fps ?? 144;
const step = Math.log(plan.step ?? 1.2);
const motion = new ZoomMotion(Math.log(plan.max ?? 20));
motion.reset(Math.log(plan.start ?? 1), 0);

const inputs = [...plan.inputs].sort((a, b) => a.ms - b.ms);
const frames = [];
let next = 0;
const total = Math.round(plan.seconds * fps);
for (let frame = 1; frame <= total; frame++) {
    const seconds = frame / fps;
    while (next < inputs.length && inputs[next].ms / 1000 <= seconds) {
        const {ms, kind, value} = inputs[next++];
        const at = ms / 1000;
        if (kind === 'wheel')
            motion.wheel(value, step, at);
        else if (kind === 'touch')
            motion.touch(value, at);
        else if (kind === 'lift')
            motion.release(at);
        else if (kind === 'glide')
            motion.glideTo(Math.log(value), at);
        else
            throw new Error(`unknown input ${kind}`);
    }
    const stall = plan.stalls?.find(s => s.frame === frame);
    const at = stall ? seconds + stall.ms / 1000 : seconds;
    frames.push({ms: at * 1000, zoom: Math.exp(motion.step(at)), settled: motion.settled});
}
print(JSON.stringify(frames));
System.exit(0);
