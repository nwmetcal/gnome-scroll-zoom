# Smoothing rebuilds edges from coverage in one shader pass

- Status: accepted
- Date: 2026-11-09
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
4 pixels out, an edge for each of the 16 nearest pixels, blended with cubic B-spline weights.
Where the pixels are not two tones with sharp edges, it draws clamped bicubic instead.

### Consequences

- Good: sharp text and lines at any zoom, at full frame rate (145 fps measured at
  2560x1440 and 144 Hz).
- Bad: a tone estimate that changes from one output pixel to the next can show as an
  outline; the sparse ring can miss a one-pixel stem, so a stem split across two pixel
  columns near it is drawn pale.
- Bad: it depends on Clutter's offscreen padding rule to place the texture, which
  `vfunc_paint_target` mirrors.

### Checked by

SZ-004 compares the drawn text, a gradient, and the alignment with GNOME's own scaling.

## Reversing it

The style setting already offers GNOME's standard scaling and plain bicubic; removing the
text style is a change to `smoothing.js` alone.
