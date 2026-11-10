# Zoom glides in log space on the frame clock

- Status: accepted
- Date: 2026-11-09
- Decided by: Nicholas Metcalf

## Context

GNOME's magnifier changes zoom in steps, and moves the zoomed view on a 60 Hz timer. On a
144 Hz monitor both look like jumps.

## Options

- Ease each change with the magnifier's own 100 ms animation.
- Run a glide of the extension's own each frame: a target zoom that input moves, and a view
  that eases toward it.

## Decision

A glide of its own, in log space (the natural log of the zoom factor), stepped on the stage's
frame clock, because a notch then feels the same at 2x and at 12x, a run of notches is one
motion, a touchpad fling can coast, and every frame the display draws has a new position. The
view also moves with each pointer move, coalesced to one move a frame, instead of on the
timer.

### Consequences

- Good: no jumps; acceleration and flings are a few lines of physics in `zoomMotion.js`,
  tested without a shell.
- Bad: the extension sets the magnifier's zoom every frame through its internal `_changeROI`
  (decision 0001).

### Checked by

SZ-002 judges the glide frame by frame at 144 Hz; SZ-003 checks that the view moves at the
display's rate; SZ-007 checks that GNOME's keyboard zoom glides too.

## Reversing it

Delete `zoomMotion.js` and call the magnifier's `setMagFactor` directly; the rest of the
extension does not depend on the glide.
