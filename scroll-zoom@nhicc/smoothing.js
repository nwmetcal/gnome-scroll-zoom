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
// 3. For each of the 4 nearest source pixels, fit a shape to it and its 8
//    neighbours that covers exactly as much of the pixel as its coverage
//    says, so every pixel keeps the ink it had:
//    - a straight edge across it, at the angle its coverage changes fastest,
//      or a thin band across it where the coverage peaks in it, as a serif's
//      hairline or a crossbar does;
//    - or, where an upright edge and a flat one meeting at a corner explain
//      the neighbours almost exactly and clearly better, that corner, as at
//      a stem's end;
//    - a pixel with no ink, or all ink, takes the edges its neighbours give.
// 4. Blend the 4 shapes' distances only near the pixels' shared edges, and
//    draw the dark tone wherever the blend says "inside", with a
//    1-screen-pixel antialiased border.
// Blending each pixel's shape only with its nearest neighbours keeps a
// stem's ends and a serif's corners square and a hairline as thin as the
// font draws it; a stem that falls across two pixel columns as two
// half-gray columns still comes back as one solid stroke of the right width.
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

// For each of the 4 pixels around the sample point: its shape's signed
// distance at the sample point, weighted toward the nearest pixel, and only
// shared with a neighbour within SHARED source pixels of their common edge.
const SHARED = 0.3;

function generateShapes() {
    let code = 'float d = 0.0; float steepest = 0.0; float g = 0.0;\n';
    code += `vec2 share = clamp((f - 0.5) / ${SHARED.toFixed(2)} + 0.5, 0.0, 1.0);\n`;
    for (const j of [0, 1]) {
        for (const i of [0, 1]) {
            const row = dj => `vec3(${[-1, 0, 1].map(di => `cv[${block(i + di, j + dj)}]`).join(', ')})`;
            const wx = i ? 'share.x' : '(1.0 - share.x)';
            const wy = j ? 'share.y' : '(1.0 - share.y)';
            code += `d += ${wx} * ${wy} * sz_shape(f - vec2(${num(i)}, ${num(j)}), ${row(-1)}, ${row(0)}, ${row(1)}, half_width, g);\n`;
            code += 'steepest = max(steepest, g);\n';
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

// Catmull-Rom weights for the four taps around fraction t.
vec4 sz_cubic(float t) {
    float t2 = t * t;
    float t3 = t2 * t;
    return vec4(-0.5 * t3 + t2 - 0.5 * t,
                1.5 * t3 - 2.5 * t2 + 1.0,
                -1.5 * t3 + 2.0 * t2 + 0.5 * t,
                0.5 * t3 - 0.5 * t2);
}

// Shapes are measured in source pixels from the pixel's centre, positive
// inside the dark tone. Each takes the pixel's 3x3 coverage as three rows,
// top to bottom, each from left (x) to right (z).

// Along one axis: the ink in a pixel covered x, between neighbours covered a
// (before) and b (after). Ink that goes on into a neighbour touches that side;
// ink on neither side is a band in the middle; ink on both sides leaves a gap
// in the middle, closed when the pixel is nearly full.
float sz_interval(float t, float a, float x, float b, float half_width) {
    float ta = smoothstep(0.0, 0.06, a);
    float tb = smoothstep(0.0, 0.06, b);
    float none = min(0.5 * x, x - half_width) - abs(t);
    float before = min(t + 0.5 + a, x - 0.5 - t);
    float after = min(t - 0.5 + x, 0.5 + b - t);
    float s = max(a + b, 0.000001);
    float gap = max(min(t + 0.5 + a, x * a / s - 0.5 - t),
                    min(t - 0.5 + x * b / s, 0.5 + b - t));
    float full = min(t + 0.5 + a, 0.5 + b - t);
    float both = mix(gap, full, smoothstep(0.75, 0.95, x));
    return mix(mix(none, before, ta), mix(after, both, ta), tb);
}

// Splits the 3x3 into a profile across (X) times a profile down (Y), through
// the pixel, so X.y * Y.y is its own coverage. The steadier profile reaches 1:
// a stem's edge is a column of the same coverage, not a band across. Returns
// how far the product is from the 3x3.
float sz_factor(vec3 top, vec3 mid, vec3 bot, out vec3 X, out vec3 Y) {
    float c = max(mid.y, 0.000001);
    vec3 col = vec3(top.y, mid.y, bot.y);
    float rmax = max(max(mid.x, mid.y), mid.z);
    float cmax = max(max(col.x, col.y), col.z);
    float rspread = rmax - min(min(mid.x, mid.y), mid.z);
    float cspread = cmax - min(min(col.x, col.y), col.z);
    float lo = rmax;
    float hi = c / max(cmax, 0.000001);
    float scale = cspread <= rspread ? hi : lo;
    scale = max(lo <= hi ? clamp(scale, lo, hi) : 0.5 * (lo + hi), 0.000001);
    X = clamp(mid / scale, 0.0, 1.0);
    Y = clamp(col * scale / c, 0.0, 1.0);
    vec3 e0 = X * Y.x - top;
    vec3 e1 = X * Y.y - mid;
    vec3 e2 = X * Y.z - bot;
    return dot(e0, e0) + dot(e1, e1) + dot(e2, e2);
}

// How much of a pixel's square lies beyond offset o along unit normal n.
// Projected onto n the square spans -s..s with sloped ends 'a' wide, so the
// area is quadratic near the ends, linear between.
float sz_area_beyond(float o, vec2 n) {
    float a = min(abs(n.x), abs(n.y));
    float b = max(abs(n.x), abs(n.y));
    float s = 0.5 * (a + b);
    float ab2 = max(2.0 * a * b, 0.000001);
    if (o >= s)
        return 0.0;
    if (o <= -s)
        return 1.0;
    if (o > s - a)
        return (s - o) * (s - o) / ab2;
    if (o < a - s)
        return 1.0 - (o + s) * (o + s) / ab2;
    return clamp((s - 0.5 * a - o) / max(b, 0.000001), 0.0, 1.0);
}

// The offset along unit normal n of the straight edge that leaves a fraction
// c of the pixel's square on the side n points to.
float sz_edge_offset(float c, vec2 n) {
    float a = min(abs(n.x), abs(n.y));
    float b = max(abs(n.x), abs(n.y));
    float s = 0.5 * (a + b);
    float corner = a / (2.0 * b);
    if (c <= corner)
        return s - sqrt(2.0 * a * b * c);
    if (c >= 1.0 - corner)
        return sqrt(2.0 * a * b * (1.0 - c)) - s;
    return s - 0.5 * a - b * c;
}

float sz_half_error(vec2 v, float c, float o, vec2 n) {
    float e = sz_area_beyond(o - dot(v, n), n) - c;
    return e * e;
}

// Coverage of the 3x3 at offset v from its centre, between pixel centres.
float sz_coverage_at(vec2 v, vec3 top, vec3 mid, vec3 bot) {
    vec3 wx = vec3(max(-v.x, 0.0), 1.0 - abs(v.x), max(v.x, 0.0));
    vec3 wy = vec3(max(-v.y, 0.0), 1.0 - abs(v.y), max(v.y, 0.0));
    return dot(wy, vec3(dot(wx, top), dot(wx, mid), dot(wx, bot)));
}

// How far a thin band of width w across normal m through the pixel's centre
// is from the neighbour at v's coverage; only neighbours across the band
// count, since a band's width may change along it.
float sz_band_error(vec2 v, float c, float w, vec2 m) {
    float along = dot(v, m);
    float e = clamp(1.0 - sz_area_beyond(0.5 * w - along, m)
        - sz_area_beyond(0.5 * w + along, m), 0.0, 1.0) - c;
    return abs(along) > 0.7 ? e * e : 0.0;
}

// The straight edge or thin band: its distance at q, and in 'error' how far
// it is from explaining the neighbours.
float sz_slanted(vec2 q, vec3 top, vec3 mid, vec3 bot, float half_width,
                 out float error, out float steep) {
    float c = mid.y;
    // Scharr, which gets edge angles right more evenly than Sobel.
    vec2 g = vec2(3.0 * (top.z - top.x) + 10.0 * (mid.z - mid.x) + 3.0 * (bot.z - bot.x),
                  3.0 * (bot.x - top.x) + 10.0 * (bot.y - top.y) + 3.0 * (bot.z - top.z)) / 32.0;
    steep = length(g);
    vec2 n = steep > 0.000001 ? g / steep : vec2(0.0, 1.0);
    float o = sz_edge_offset(c, n);
    float edge = dot(q, n) - o;
    float edge_error = sz_half_error(vec2(-1.0, -1.0), top.x, o, n)
        + sz_half_error(vec2(0.0, -1.0), top.y, o, n) + sz_half_error(vec2(1.0, -1.0), top.z, o, n)
        + sz_half_error(vec2(-1.0, 0.0), mid.x, o, n) + sz_half_error(vec2(1.0, 0.0), mid.z, o, n)
        + sz_half_error(vec2(-1.0, 1.0), bot.x, o, n) + sz_half_error(vec2(0.0, 1.0), bot.y, o, n)
        + sz_half_error(vec2(1.0, 1.0), bot.z, o, n);

    // Where the coverage peaks in this pixel, the direction it falls off
    // fastest (the Hessian's most negative eigenvalue) is across the band.
    float hxx = mid.z + mid.x - 2.0 * c;
    float hyy = bot.y + top.y - 2.0 * c;
    float hxy = 0.25 * (bot.z + top.x - top.z - bot.x);
    float lambda = 0.5 * (hxx + hyy) - sqrt(max(0.25 * (hxx - hyy) * (hxx - hyy) + hxy * hxy, 0.0));
    vec2 v1 = vec2(hxy, lambda - hxx);
    vec2 v2 = vec2(lambda - hyy, hxy);
    vec2 m = dot(v1, v1) > dot(v2, v2) ? v1 : v2;
    m = length(m) > 0.000001 ? normalize(m) : vec2(0.0, 1.0);
    float a = min(abs(m.x), abs(m.y));
    float b = max(abs(m.x), abs(m.y));
    float s = 0.5 * (a + b);
    float h = s - 0.5 * a - 0.5 * b * (1.0 - c);
    h = h <= s - a ? h : s - sqrt(max(a * b * (1.0 - c), 0.0));
    float w = max(2.0 * h, 0.0);
    // Ink in the pixels on either side across it carries the band on into them,
    // as a stroke wider than the pixel does.
    float band = sz_interval(dot(q, m), sz_coverage_at(-m, top, mid, bot), w,
                             sz_coverage_at(m, top, mid, bot), half_width);
    float band_error = sz_band_error(vec2(-1.0, -1.0), top.x, w, m)
        + sz_band_error(vec2(0.0, -1.0), top.y, w, m) + sz_band_error(vec2(1.0, -1.0), top.z, w, m)
        + sz_band_error(vec2(-1.0, 0.0), mid.x, w, m) + sz_band_error(vec2(1.0, 0.0), mid.z, w, m)
        + sz_band_error(vec2(-1.0, 1.0), bot.x, w, m) + sz_band_error(vec2(0.0, 1.0), bot.y, w, m)
        + sz_band_error(vec2(1.0, 1.0), bot.z, w, m);

    // Flat pixels have no edge direction: inside or outside by coverage.
    bool partial = c > 0.02 && c < 0.98;
    float flat_distance = partial ? 2.0 * c - 1.0 : (c > 0.5 ? 1.0 : -1.0);
    float ridge = smoothstep(0.1, 0.3, -lambda);
    float along = smoothstep(0.03, 0.12, steep);
    error = mix(ridge > 0.0 ? band_error : 0.0, edge_error, along);
    return mix(mix(flat_distance, band, ridge), edge, along);
}

// One pixel's shape at q: the straight edge or band, unless an upright edge
// and a flat one meeting at a corner explain the neighbours almost exactly and
// clearly better, as at a stem's end. Text's corners are upright and flat;
// a curve or a slanted stroke is never that exact, and drawn as corners it
// would show steps.
float sz_shape(vec2 q, vec3 top, vec3 mid, vec3 bot, float half_width, out float steep) {
    vec3 X;
    vec3 Y;
    float corner_error = sz_factor(top, mid, bot, X, Y);
    float corner = min(sz_interval(q.x, X.x, X.y, X.z, half_width),
                       sz_interval(q.y, Y.x, Y.y, Y.z, half_width));
    // Ink in either of an upright structure and a flat one: what an empty
    // pixel's neighbours reach into it with.
    vec3 PX;
    vec3 PY;
    sz_factor(1.0 - top, 1.0 - mid, 1.0 - bot, PX, PY);
    float join = max(sz_interval(q.x, 1.0 - PX.x, 1.0 - PX.y, 1.0 - PX.z, half_width),
                     sz_interval(q.y, 1.0 - PY.x, 1.0 - PY.y, 1.0 - PY.z, half_width));
    float slanted_error;
    float d = sz_slanted(q, top, mid, bot, half_width, slanted_error, steep);
    float use_corner = smoothstep(0.0, 0.1, slanted_error - corner_error - 0.1)
        * (1.0 - smoothstep(0.02, 0.06, corner_error));
    d = mix(d, corner, use_corner);
    // A pixel with no ink has none of its own, and nears its neighbours' ink
    // only where it reaches its edge; beyond its edge, its neighbour's shape
    // decides. A pixel all ink is the same with ink and paper swapped.
    d = mix(d, min(join, 0.0), 1.0 - smoothstep(0.0, 0.03, mid.y));
    return mix(d, max(corner, 0.0), smoothstep(0.97, 1.0, mid.y));
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
    // An antialiased border sz_edge screen pixels wide; one source pixel
    // spans sz_mag screen pixels.
    float half_width = clamp(0.5 * sz_edge / sz_mag, 0.01, 0.75);
    ${generateShapes()}
    d += sz_weight - 0.5;

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
