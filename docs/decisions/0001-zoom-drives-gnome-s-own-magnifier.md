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

How the view follows the pointer stays GNOME's own setting, Follow Behavior, which GNOME's
Settings page shows. A setting of Scroll Zoom's own for it would override that page without a
word, which the switches for focus and the text cursor can do only because the page shows
neither. Scroll Zoom adds one thing to GNOME's following: under push, zooming with Super and the
wheel or a touchpad, and zoom coming on, keep the pointer where it is on the screen, where
GNOME's own push zooms around the view's middle and pushes the pointer toward an edge
(SZ-010). GNOME's keyboard zoom and its Settings slider still zoom GNOME's way.

### Consequences

- Good: zoom on and off and the zoom level are GNOME's settings, so the toggle and the
  Settings slider stay in step with the wheel.
- Bad: the extension reaches into the magnifier's internals (`_changeROI`, the zoom region's
  clone, `_updateCloneGeometry`, the pointer image's size, `_mouseSourceActor`, where its view
  lies, `_viewPortX` and its kin, and whether it holds the view within the screen,
  `_clampScrollingAtEdges`), which can change between GNOME releases. That is why
  `metadata.json` lists only the versions the `@shell` scenarios have passed on.

### Checked by

SZ-001 and SZ-007 drive GNOME's zoom settings; SZ-006 checks that turning the extension off
hands the magnifier back unchanged; SZ-001 checks GNOME's centred following, and SZ-010 checks
push and that moving with the contents and none place the view as GNOME does.

## Reversing it

A zoom of its own would need everything above rewritten: tracking, shortcuts, settings. The
seam is that the extension touches the magnifier in a few places: `RegionSmoothing` in
`smoothing.js`, and `_applyLevel`, `_onActiveChanged`, `_pushCentre`, `_routeMagFactorChanges`,
and `_routeFollowing` and the handlers it connects (decision 0007) in `extension.js`.
