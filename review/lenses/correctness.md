# The correctness lens

Break the change. Find the input, the state, or the order of events under which it does the
wrong thing, and prove it with a run. Every change outside the documentation needs this lens.

- **Input.** The wheel, a high-resolution wheel, a touchpad, keyboard zoom, and the Settings
  slider; the keys held and the keys not held; events that arrive twice, late, or out of
  order; a key released mid-glide.
- **Limits.** 1x, the maximum zoom, one notch past each; zoom turned on or off by GNOME while
  a glide runs; a zoom level set outside the extension.
- **Lifecycle.** The extension turned off and on mid-glide, with zoom on, and around a screen
  lock. Everything it connected, added, or patched is undone when it is turned off, and GNOME's
  magnifier works as it did before.
- **Drawing.** Where the zoomed view lands against GNOME's own, to the pixel. Text, thin lines,
  light on dark, colored text, photos, and gradients. Lens mode and the half-screen positions
  as well as full screen. The cost of a frame at the display's size and rate.
- **Numbers.** Time in ms against seconds against microseconds; zoom factors against their
  logs; texture coordinates against stage pixels.
- **Settings.** A setting changed while zoomed takes effect at once; a setting left at an
  unknown value falls back to a stated default.

A worry that could not be turned into a failing run is a note, not a blocking finding.
