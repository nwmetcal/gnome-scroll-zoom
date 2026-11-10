# Zoom follows keyboard focus and the text cursor only when asked, and no further than it must

- Status: accepted
- Date: 2026-11-10
- Decided by: the owner, on the defaults; the loop, on how

## Context

GNOME's zoom follows keyboard focus and the text cursor unless told otherwise. When either
moves while the pointer has moved in the last second, GNOME waits until the pointer has rested
a second, then jumps the view there. A terminal moves its text cursor each time it prints, so
the view keeps leaving what the person is reading; in the test shell, one Tab press moved the
view 547 pixels from the pointer. The owner, who uses zoom every day, called this snapping
"super frustrating". Losing one's place is the main cost of full-screen zoom for people with
low vision (Billah and others, "SteeringWheel: A Locality-Preserving Magnification Interface
for Low Vision Web Browsing", CHI 2018), and a jump to another part of the screen is the
costliest kind.

The question: should Scroll Zoom follow focus and the text cursor by default, and how, given
that it writes no setting of GNOME's but zoom on or off and the zoom level (AGENTS.md)?

## Options

- Leave following to GNOME's own settings, and tell people where to turn it off.
- Two switches of Scroll Zoom's own, off by default. Turned on, each moves the view the way
  GNOME's settings say, centred or in proportion.
- Two switches of Scroll Zoom's own, off by default. Turned on, each moves the view only as far
  as it takes to show the whole of what moved, whatever GNOME's settings say.

## Decision

The third. Off by default, because a view that stays where the pointer puts it is what the
person asked for and what keeps their place. When on, the least move that shows the whole of
what moved, with 24 pixels of room, because it keeps what was in view close by. GNOME's own
push was tried first and fell short: it pushes until the middle of what moved reaches the
view's edge, which leaves three quarters of a control above or left of the view out of it, and
it skips a move to where it saw the last one.

Scroll Zoom answers the calls GNOME's magnifier makes to set its zoom region's following, at
the shell's start and on every change to GNOME's settings, with its own switches, as it already
answers `setMagFactor`. With a switch on, GNOME still listens for focus and the text cursor and
still waits for the pointer to rest, but Scroll Zoom places the view, from the size and place
GNOME's accessibility gives what moved. A follow GNOME was holding back is dropped when a
switch changes or Scroll Zoom comes on. GNOME's settings are never written, and turning the
extension off hands them back. This changes decision 0001, whose list of what keeps working under Scroll Zoom no
longer names focus and caret tracking.

### Consequences

- Good: no snapping out of the box, whatever GNOME's settings say, and no settings of GNOME's
  changed.
- Good: someone who wants following gets it with one switch, and it moves the view no more
  than it must.
- Bad: while Scroll Zoom is on, GNOME's own choice of centred or proportional following for
  focus and the text cursor has no effect.
- Bad: it leans on more of GNOME's zoom region's insides: `setFocusTrackingMode` and
  `setCaretTrackingMode` being what its magnifier calls, its `_focusCaretTracker` and its
  signals, `_convertExtentsToScreenSpace`, `_centerFromFocusPosition`,
  `_centerFromCaretPosition`, `_scrollContentsToDelayed`, and the follow it holds in
  `_xDelayed` and `_yDelayed`. A future GNOME could change any of them, and SZ-009 is what
  would show it.

### Checked by

SZ-009's scenarios fail if the view follows focus or the text cursor with the switches off,
follows further than it takes with one on, follows the other kind of move, or comes back after
GNOME's settings change, if GNOME's settings are written, or if turning Scroll Zoom off does not
hand GNOME's following back.

## Reversing it

Remove the two switches, `_routeFollowing`, and the handlers it connects in `extension.js`,
and GNOME's settings decide following again. To follow by default instead, change the two defaults in the schema and the
scenarios of SZ-009 that assume them, in a commit of their own that says why.
