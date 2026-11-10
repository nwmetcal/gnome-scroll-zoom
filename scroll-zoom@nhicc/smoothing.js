// SPDX-License-Identifier: GPL-2.0-or-later
// Image smoothing for the zoomed view, like macOS's "Smooth images".
//
// GNOME's magnifier draws a copy of the whole screen scaled up, so the GPU
// stretches every window with bilinear filtering and text turns blurry.
// Instead, this keeps that copy at 1x, renders it into an offscreen texture at
// full resolution, and draws the zoomed view with a shader that rebuilds the
// shapes of text and line art.
//
// How the "text" style rebuilds an edge, per output pixel:
// 1. Find the two tones nearby (the darkest and lightest of the 6x6 source
//    pixels around it), e.g. ink and paper.
// 2. Read each source pixel's color as coverage: how much of it the dark tone
//    covers. Antialiased text is drawn exactly that way.
// 3. For each of the 16 nearest source pixels, the direction its coverage
//    changes fastest gives the edge's angle, and the coverage gives where
//    the edge cuts through it: the straight edge at that angle that leaves
//    exactly that much of the pixel dark.
// 4. Blend the distances to those 16 edges (smoothly, weighted toward the
//    nearest) and draw the dark tone wherever the blend says "inside", with
//    a 1-screen-pixel antialiased border.
// A stem that falls across two pixel columns as two half-gray columns comes
// back as one solid stroke of the right width, and curves stay smooth.
//
// Where the 6x6 pixels don't look like two tones with sharp edges (photos,
// gradients, soft shadows), it keeps a smooth bicubic estimate instead,
// clamped to the nearest pixels' colors so there are no halos.

import Cogl from 'gi://Cogl';
import GObject from 'gi://GObject';
import Shell from 'gi://Shell';

export const Mode = {
    PIXELS: 0,   // nearest neighbour: hard pixels, like "Smooth images" off
    BILINEAR: 1, // what GNOME does by default
    SOFT: 2,     // bicubic
    TEXT: 3,     // edge rebuilding for text and line art, bicubic elsewhere
};

// The shader reads a 6x6 block of source pixels, offsets -2..3 from the
// pixel at or before the sample point. GLSL has no convenient loops over
// arrays everywhere Cogl runs, so the repetitive parts are generated here.
const LO = -2;
const SIZE = 6;
const block = (i, j) => (j - LO) * SIZE + (i - LO);
const num = n => `${n}.0`;
const range = (from, to) => Array.from({length: to - from + 1}, (_, k) => from + k);

function generateFetches() {
    let code = '';
    for (const j of range(LO, LO + SIZE - 1)) {
        for (const i of range(LO, LO + SIZE - 1)) {
            const n = block(i, j);
            code += `col[${n}] = sz_fetch(base + vec2(${num(i)}, ${num(j)})); lum[${n}] = sz_luma(col[${n}]);\n`;
        }
    }
    return code;
}

function generateTones() {
    let code = 'float dark_l = lum[0]; vec4 dark = col[0]; float light_l = lum[0]; vec4 light = col[0];\n';
    for (const n of range(1, SIZE * SIZE - 1)) {
        code += `if (lum[${n}] < dark_l) { dark_l = lum[${n}]; dark = col[${n}]; }\n`;
        code += `if (lum[${n}] > light_l) { light_l = lum[${n}]; light = col[${n}]; }\n`;
    }
    return code;
}

function generateBicubic() {
    const w = ['x', 'y', 'z', 'w'];
    let code = 'vec4 soft = vec4(0.0);\n';
    for (const j of range(-1, 2)) {
        for (const i of range(-1, 2))
            code += `soft += col[${block(i, j)}] * (wx.${w[i + 1]} * wy.${w[j + 1]});\n`;
    }
    return code;
}

// 16 more pixels 4 away, to find the ink of strokes too thin to have one
// fully covered pixel in the 6x6 block.
function generateWideTones() {
    let code = 'float wide_dark_l = 2.0; vec4 wide_dark = dark; float wide_light_l = -1.0; vec4 wide_light = light;\n';
    for (const j of [-4, -2, 0, 2, 4]) {
        for (const i of [-4, -2, 0, 2, 4]) {
            if (Math.abs(i) !== 4 && Math.abs(j) !== 4)
                continue;
            code += `{ vec4 c = sz_fetch(base + vec2(${num(i)}, ${num(j)})); float l = sz_luma(c);
                if (l < wide_dark_l) { wide_dark_l = l; wide_dark = c; }
                if (l > wide_light_l) { wide_light_l = l; wide_light = c; } }\n`;
        }
    }
    return code;
}

function generateCoverage() {
    let code = '';
    for (const n of range(0, SIZE * SIZE - 1))
        code += `cv[${n}] = clamp((light_l - lum[${n}]) / tone_range, 0.0, 1.0);\n`;
    return code;
}

// For each of the 16 pixels around the sample point: the coverage gradient
// (Scharr, which gets edge angles right more evenly than Sobel), that pixel's
// edge distance, and its share of the blend. Cubic B-spline weights are
// smooth and never negative, so neighbouring pixels' slightly different
// edge estimates average out instead of showing as bumps, and straight edges
// stay exactly straight.
function generateEdgeBlend() {
    const w = ['x', 'y', 'z', 'w'];
    let code = 'float d = 0.0; float steepest = 0.0;\n';
    for (const j of range(-1, 2)) {
        for (const i of range(-1, 2)) {
            const c = (di, dj) => `cv[${block(i + di, j + dj)}]`;
            code += `{ vec2 g = vec2(
                3.0 * (${c(1, -1)} - ${c(-1, -1)}) + 10.0 * (${c(1, 0)} - ${c(-1, 0)}) + 3.0 * (${c(1, 1)} - ${c(-1, 1)}),
                3.0 * (${c(-1, 1)} - ${c(-1, -1)}) + 10.0 * (${c(0, 1)} - ${c(0, -1)}) + 3.0 * (${c(1, 1)} - ${c(1, -1)})) / 32.0;
              d += (bx.${w[i + 1]} * by.${w[j + 1]}) * sz_edge_distance(p, base + vec2(${num(i)}, ${num(j)}), ${c(0, 0)}, g);\n`;
            if (i >= 0 && i <= 1 && j >= 0 && j <= 1)
                code += '  steepest = max(steepest, length(g));\n';
            code += '}\n';
        }
    }
    return code;
}

const DECLARATIONS = `
uniform vec2 sz_offset;   // texture coordinate shown at the view's top-left
uniform float sz_mag;
uniform vec2 sz_texel;    // one source pixel, texture coordinates
uniform float sz_mode;
uniform float sz_edge;    // edge width, in screen pixels
uniform float sz_weight;  // 0.5 = true stroke width; higher = bolder dark strokes

vec4 sz_fetch(vec2 index) {
    return texture2D(cogl_sampler0, (index + 0.5) * sz_texel);
}

float sz_luma(vec4 c) {
    return dot(c.rgb, vec3(0.2126, 0.7152, 0.0722));
}

// How far color c is from the line between colors a and b, as a fraction of
// the distance from a to b.
float sz_line_distance(vec4 c, vec4 a, vec4 b) {
    vec3 ab = b.rgb - a.rgb;
    float t = clamp(dot(c.rgb - a.rgb, ab) / max(dot(ab, ab), 0.000001), 0.0, 1.0);
    return length(c.rgb - (a.rgb + ab * t)) / max(length(ab), 0.001);
}

// Cubic B-spline weights for the four taps around fraction t.
vec4 sz_bspline(float t) {
    float t2 = t * t;
    float t3 = t2 * t;
    float u = 1.0 - t;
    return vec4(u * u * u, 3.0 * t3 - 6.0 * t2 + 4.0, -3.0 * t3 + 3.0 * t2 + 3.0 * t + 1.0, t3) / 6.0;
}

// Catmull-Rom weights for the four taps around fraction t.
vec4 sz_cubic(float t) {
    float t2 = t * t;
    float t3 = t2 * t;
    return vec4(-0.5 * t3 + t2 - 0.5 * t,
                1.5 * t3 - 2.5 * t2 + 1.0,
                -1.5 * t3 + 2.0 * t2 + 0.5 * t,
                0.5 * t3 - 0.5 * t2);
}

// Signed distance (source pixels, positive = dark side) from point q to the
// edge through the pixel at 'center' with dark coverage c and coverage
// gradient g: the straight edge, perpendicular to g, that leaves a fraction c
// of the pixel's square on the dark side.
float sz_edge_distance(vec2 q, vec2 center, float c, vec2 g) {
    // Flat pixels have no edge direction: inside or outside by coverage.
    float flat_distance = 2.0 * c - 1.0;
    float g_len = length(g);
    if (g_len < 0.001)
        return flat_distance;

    vec2 n = g / g_len;
    float a = min(abs(n.x), abs(n.y));
    float b = max(abs(n.x), abs(n.y));
    // Projected onto n, the square spans -s..s with sloped ends 'a' wide, so
    // the area beyond offset o is quadratic near the ends, linear between.
    float s = 0.5 * (a + b);
    float corner = a / (2.0 * b);
    float o;
    if (c <= corner)
        o = s - sqrt(2.0 * a * b * c);
    else if (c >= 1.0 - corner)
        o = sqrt(2.0 * a * b * (1.0 - c)) - s;
    else
        o = s - 0.5 * a - b * c;

    float edge_distance = dot(q - center, n) - o;
    return mix(flat_distance, edge_distance, smoothstep(0.02, 0.1, g_len));
}

vec4 sz_filter(vec2 uv) {
    vec2 p = uv / sz_texel - 0.5;
    vec2 base = floor(p);
    vec2 f = p - base;

    if (sz_mode < 0.5)
        return sz_fetch(floor(uv / sz_texel));

    if (sz_mode < 1.5) {
        vec4 top = mix(sz_fetch(base), sz_fetch(base + vec2(1.0, 0.0)), f.x);
        vec4 bottom = mix(sz_fetch(base + vec2(0.0, 1.0)), sz_fetch(base + vec2(1.0, 1.0)), f.x);
        return mix(top, bottom, f.y);
    }

    vec4 col[${SIZE * SIZE}];
    float lum[${SIZE * SIZE}];
    ${generateFetches()}

    vec4 wx = sz_cubic(f.x);
    vec4 wy = sz_cubic(f.y);
    ${generateBicubic()}
    // Clamp to the 4 nearest pixels' colors: no ringing or halos.
    vec4 near_lo = min(min(col[${block(0, 0)}], col[${block(1, 0)}]), min(col[${block(0, 1)}], col[${block(1, 1)}]));
    vec4 near_hi = max(max(col[${block(0, 0)}], col[${block(1, 0)}]), max(col[${block(0, 1)}], col[${block(1, 1)}]));
    soft = clamp(soft, near_lo, near_hi);
    if (sz_mode < 2.5)
        return soft;

    ${generateTones()}
    // A stem split across two pixel columns can be paler than its ink
    // everywhere in the 6x6 block. A darker tone a few pixels away that the
    // local one is a blend of (with the light tone) is the same ink.
    ${generateWideTones()}
    if (wide_dark_l < dark_l - 0.03 && sz_line_distance(dark, wide_dark, light) < 0.08) {
        dark = wide_dark;
        dark_l = wide_dark_l;
    }
    if (wide_light_l > light_l + 0.03 && sz_line_distance(light, dark, wide_light) < 0.08) {
        light = wide_light;
        light_l = wide_light_l;
    }
    float tone_range = light_l - dark_l;
    if (tone_range < 0.04)
        return soft;

    float cv[${SIZE * SIZE}];
    ${generateCoverage()}
    vec4 bx = sz_bspline(f.x);
    vec4 by = sz_bspline(f.y);
    ${generateEdgeBlend()}
    d += sz_weight - 0.5;

    // An antialiased border sz_edge screen pixels wide; one source pixel
    // spans sz_mag screen pixels.
    float half_width = clamp(0.5 * sz_edge / sz_mag, 0.01, 0.75);
    vec4 sharp = mix(light, dark, smoothstep(-half_width, half_width, d));

    // Rebuild only text-like areas: enough contrast, sharp edges (a smooth
    // gradient changes slowly), and colors that are blends of the two tones
    // (not a photo's many hues).
    float off_line = length(soft.rgb - mix(dark.rgb, light.rgb,
        clamp((sz_luma(soft) - dark_l) / tone_range, 0.0, 1.0))) / tone_range;
    float strength = smoothstep(0.06, 0.2, tone_range)
        * smoothstep(0.12, 0.25, steepest)
        * (1.0 - smoothstep(0.15, 0.4, off_line));
    // Debugging aids, not offered in settings: 4 shows where edges are
    // rebuilt (white = fully), 5 shows rebuilt edges everywhere.
    if (sz_mode > 4.5)
        return sharp;
    if (sz_mode > 3.5)
        return vec4(vec3(strength), 1.0);
    return mix(soft, sharp, strength);
}
`;

const CODE = `
vec2 sz_uv = sz_offset + cogl_tex_coord_in[0].xy / sz_mag;
cogl_color_out = sz_filter(sz_uv) * cogl_color_in;
`;

export const SmoothZoomEffect = GObject.registerClass(
class SmoothZoomEffect extends Shell.GLSLEffect {
    _init(params) {
        super._init(params);
        this._uniforms = {};
        for (const name of ['offset', 'mag', 'texel', 'mode', 'edge', 'weight'])
            this._uniforms[name] = this.get_uniform_location(`sz_${name}`);
        this._view = null;
        this.setStyle(Mode.TEXT, 1.0, 0.5);
    }

    vfunc_build_pipeline() {
        this.add_glsl_snippet(Cogl.SnippetHook.FRAGMENT, DECLARATIONS, CODE, true);
    }

    // Where the offscreen texture sits is only known once it has been drawn.
    vfunc_paint_target(node, paintContext) {
        const texture = this.get_texture();
        const actor = this.get_actor();
        const [hasBox, box] = actor?.get_paint_box() ?? [false, null];
        if (texture && hasBox && this._view) {
            // Clutter pads offscreen textures for rounding (see
            // _clutter_actor_box_enlarge_for_effects): the bottom-right edge is
            // at ceil(edge + 0.75) device pixels, and the texture extends up and
            // left from there.
            const scale = Math.ceil(actor.get_resource_scale());
            const width = texture.get_width();
            const height = texture.get_height();
            const left = (Math.ceil(box.x2 * scale + 0.75) - width) / scale;
            const top = (Math.ceil(box.y2 * scale + 0.75) - height) / scale;
            const [actorX, actorY] = actor.get_transformed_position();
            const {centerX, centerY, halfWidth, halfHeight, mag} = this._view;

            // A point at stage x on screen shows the screen-copy point at
            // centerX + (x - actorX - halfWidth) / mag, which is in the texture
            // at actorX + that - left. With x = left + u * width / scale for
            // texture coordinate u, the shown coordinate is offset + u / mag.
            const offsetX = (actorX + centerX - left + (left - actorX - halfWidth) / mag) * scale / width;
            const offsetY = (actorY + centerY - top + (top - actorY - halfHeight) / mag) * scale / height;
            this._set('offset', [offsetX, offsetY]);
            this._set('texel', [1 / width, 1 / height]);
        }
        super.vfunc_paint_target(node, paintContext);
    }

    // centerX/Y: the screen point shown in the middle of the view. halfWidth/
    // Height: half the view's size. All in stage pixels.
    setView(centerX, centerY, halfWidth, halfHeight, mag) {
        this._view = {centerX, centerY, halfWidth, halfHeight, mag};
        this._set('mag', [mag]);
        this.queue_repaint();
    }

    setStyle(mode, edgeWidth, weight) {
        this._set('mode', [mode]);
        this._set('edge', [edgeWidth]);
        this._set('weight', [weight]);
        this.queue_repaint();
    }

    _set(name, values) {
        this.set_uniform_float(this._uniforms[name], values.length, values);
    }
});

// Swaps a magnifier zoom region's scaled copy of the screen for the 1x copy
// drawn through SmoothZoomEffect, and undoes it on remove().
export class RegionSmoothing {
    constructor(region) {
        this._region = region;
        this._effect = null;
        this._mode = Mode.TEXT;
        this._edge = 1.0;
        this._weight = 0.5;

        const self = this;
        const {_createActors, _destroyActors, _updateCloneGeometry} = region;
        this._originals = {_createActors, _destroyActors, _updateCloneGeometry};
        region._createActors = function () {
            _createActors.call(this);
            self._attach();
        };
        region._destroyActors = function () {
            self._detach();
            _destroyActors.call(this);
        };
        region._updateCloneGeometry = function (animate = false) {
            _updateCloneGeometry.call(this, animate);
            self._sync();
        };

        if (region.isActive()) {
            this._attach();
            region._updateCloneGeometry();
        }
    }

    setStyle(mode, edgeWidth, weight) {
        this._mode = mode;
        this._edge = edgeWidth;
        this._weight = weight;
        this._effect?.setStyle(mode, edgeWidth, weight);
    }

    remove() {
        this._detach();
        for (const name of Object.keys(this._originals))
            delete this._region[name];
        if (this._region.isActive())
            this._region._updateCloneGeometry();
    }

    _attach() {
        const clone = this._region._uiGroupClone;
        if (!clone || this._effect)
            return;
        this._effect = new SmoothZoomEffect();
        this._effect.setStyle(this._mode, this._edge, this._weight);
        clone.add_effect_with_name('scroll-zoom-smoothing', this._effect);
    }

    _detach() {
        if (!this._effect)
            return;
        this._region._uiGroupClone?.remove_effect(this._effect);
        this._effect = null;
    }

    // Undo the magnifier's scaling of the copy (the shader does the zooming),
    // then point the shader at the current magnified area.
    _sync() {
        const region = this._region;
        const clone = region._uiGroupClone;
        if (!this._effect || !clone)
            return;

        clone.remove_all_transitions();
        clone.set_scale(1, 1);
        clone.set_position(0, 0);

        this._effect.setView(region._xCenter, region._yCenter,
            region._viewPortWidth / 2, region._viewPortHeight / 2, region._xMagFactor);
    }
}
