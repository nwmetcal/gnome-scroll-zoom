# Zoom drives GNOME's own magnifier

- Status: accepted
- Date: 2026-11-10
- Decided by: Nicholas Metcalf

## Context

GNOME Shell has a full-screen magnifier with pointer, focus, and caret tracking, color
effects, crosshairs, a Settings page, and its own shortcuts. Scroll Zoom needs a zoom that is
driven by the scroll wheel, glides, and draws text sharply.

## Options

- Drive GNOME's magnifier (`Main.magnifier`) from an extension, and replace only how its
  zoomed view is drawn.
- Write a zoom of the extension's own: a scaled copy of the screen it manages itself.

## Decision

Drive GNOME's magnifier, because everything it already does keeps working: Super+Alt+8, the
Settings page, color effects, and the lock screen. Its following of keyboard focus and the text
cursor goes through Scroll Zoom's own switches while Scroll Zoom is on (decision 0007).

### Consequences

- Good: zoom on and off and the zoom level are GNOME's settings, so the toggle and the
  Settings slider stay in step with the wheel.
- Bad: the extension reaches into the magnifier's internals (`_changeROI`, the zoom region's
  clone, `_updateCloneGeometry`), which can change between GNOME releases. That is why
  `metadata.json` lists only the versions the `@shell` scenarios have passed on.

### Checked by

SZ-001 and SZ-007 drive GNOME's zoom settings; SZ-006 checks that turning the extension off
hands the magnifier back unchanged.

## Reversing it

A zoom of its own would need everything above rewritten: tracking, shortcuts, settings. The
seam is that the extension touches the magnifier in a few places: `RegionSmoothing` in
`smoothing.js`, and `_applyLevel`, `_routeMagFactorChanges`, and `_routeFollowing` and the
handlers it connects (decision 0007) in `extension.js`.
