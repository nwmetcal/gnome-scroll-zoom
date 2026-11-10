# Smoothing rebuilds edges from coverage in one shader pass

- Status: accepted
- Date: 2026-11-10
- Decided by: Nicholas Metcalf

## Context

GNOME's magnifier draws a scaled copy of the screen, so the GPU stretches every window with
bilinear filtering and zoomed text blurs. macOS's Smooth images draws zoomed text with clean
edges.

## Options

- Sharpen the bilinear result.
- An upscaler from games or emulators: bicubic, xBR, edge-adaptive Lanczos.
- Read antialiased pixels as coverage, rebuild each edge's position and angle from it, and
  draw it crisply at the zoomed size.

## Decision

Rebuild edges from coverage, because antialiased text is drawn by coverage: a pixel's gray
says how much of it the letter covers, so the edge's position comes back to a fraction of a
pixel, at any zoom. The copy of the screen stays at 1x inside an offscreen effect, and one
fragment shader pass draws the zoomed view: tones from a 6x6 neighbourhood and a sparse ring
4 pixels out, then a shape for each of the 4 nearest pixels, fitted to it and its 8
neighbours so that it covers exactly as much of the pixel as its coverage says. The shape is a
straight edge or a thin band across the pixel, or, where an upright edge and a flat one
meeting at a corner explain the neighbours almost exactly and clearly better, that corner; a
pixel with no ink or all ink takes the edges its neighbours give it. The 4 shapes blend only within 0.3 of a
pixel of their shared edges. Where the pixels are not two tones with sharp edges, it draws
clamped bicubic instead.

An earlier version blended a straight edge for each of the 16 nearest pixels with cubic
B-spline weights. Averaging the edges on both sides of a thin stroke, and the edges that meet
at a corner, thickened strokes, thin ones most, and rounded every corner to about a pixel's
radius, so zoomed text looked hand-lettered (issue #11).

### Consequences

- Good: sharp text and lines at any zoom, at full frame rate (142 to 144 fps measured at
  2560x1440 and 144 Hz zoomed over text, where GNOME's own scaling draws 144). Each pixel
  keeps the ink it had, so strokes keep the font's weight, a serif font's thin strokes stay
  thin, and square ends and corners stay square.
- Bad: a tone estimate that changes from one output pixel to the next can show as an
  outline; the sparse ring can miss a one-pixel stem, so a stem split across two pixel
  columns near it is drawn pale.
- Bad: shapes meet with a slight kink where two pixels' fits disagree, so a curve can show
  small steps that the 16-edge blend smoothed away.
- Bad: subpixel antialiasing's colored fringes are not two tones, so there it draws clamped
  bicubic, softer and a little heavier than the rebuilt edges.
- Bad: it depends on Clutter's offscreen padding rule to place the texture, which
  `vfunc_paint_target` mirrors.

### Checked by

SZ-004 compares the drawn text, a gradient, and the alignment with GNOME's own scaling, and
checks that square ends and corners stay square, that text keeps its weight, and that a serif
line keeps each pixel's ink and draws its thin bars as tall as their ink.

## Reversing it

The style setting already offers GNOME's standard scaling and plain bicubic; removing the
text style is a change to `smoothing.js` alone.
