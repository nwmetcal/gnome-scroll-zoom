# The requirements lens

Do the requirements say what Scroll Zoom must do, and do their scenarios fail when it does
not? A change needs this lens when its intent names a requirement, or when it changes a
feature, a requirement's steps, or what the steps share under `tests/`.

- **The feature.** It is named and titled by its `SZ-###` id, tagged `@invariant` or
  `@golden`, and `@shell` when a scenario needs GNOME Shell. Its words are a person's: keys,
  notches, frames, zoom levels, text, pixels. Not the code's. A pass mark carries its number
  and its unit, and the feature says why that mark.
- **Behavior.** The steps drive input through virtual devices and observe what a person would:
  GNOME's zoom state, the frames drawn, screenshots. A step that asserts on the extension's
  internals, or on a stand-in for the thing under test, is a finding.
- **Mutation.** Break the code each scenario claims to cover: make the glide instant, drop
  the per-frame panning, draw the text with plain scaling, invert a comparison. A scenario that
  still passes is a blocking finding, with the mutation and the run as its evidence. Revert
  every mutation.
- **Red first.** Each requirement made true failed on main's code before the change. A
  scenario is never edited to make it pass, and a requirement's change is a commit of its own.
- **Traceability.** `build/traceability.md` lists every scenario the change touches, with the
  status its intent says.

Before the code exists, the lens reviews the features alone: is each the right requirement
for its need, can it be tested, and does it leave out how it will be built?
