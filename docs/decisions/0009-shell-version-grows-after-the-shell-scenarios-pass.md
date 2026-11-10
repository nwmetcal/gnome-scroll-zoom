# shell-version grows after the shell scenarios pass

- Status: accepted
- Date: 2026-11-10
- Decided by: Nicholas Metcalf

## Context

A new GNOME Shell major comes out each March and September. GNOME Shell refuses to load an
extension whose `shell-version` does not list the running major, and extensions.gnome.org
gives each person the newest approved version that lists theirs. Scroll Zoom reaches into
the magnifier's internals (decision 0001), which any major may change, so `AGENTS.md` lets
`metadata.json` list only the versions the `@shell` scenarios have passed on. The question is
when and how a new major joins the list, and when an old one leaves it.

## Options

- Add a major once `make test-shell` passes on its stable release.
- Add it on a development release, which extensions.gnome.org allows one of.
- Add it untested, and fix what breaks once people report it.

## Decision

Add a major once `make test-shell` passes on its stable release, because a zoom that loads
and then misbehaves fails the people who rely on it, while one GNOME switches off leaves
them GNOME's own zoom.

- Try the release candidate early, on a branch that adds the major, on a machine or virtual
  machine whose `gnome-shell --version` reports it, and fix what fails there. The branch
  merges once the scenarios pass on the stable `.0`, and is released the same day, so the
  review on extensions.gnome.org starts weeks before most distributions ship that GNOME.
  Before the first of the release's month, the date check in `tests/style/test_bundle.py`
  fails on that branch, as the site's own analyzer would; the `@shell` scenarios still run.
- Never list a development release or a future one. extensions.gnome.org forbids future
  versions, and a pass on a release candidate is not a pass on the release.
- A major stays listed while each change can still be tested on it: keep a machine, virtual
  machine, or toolbox on a major that a long-term release ships, as Ubuntu 26.04 ships
  GNOME 50. A change that cannot pass on an older major removes it. People still on that
  major keep the last approved version that lists it, because extensions.gnome.org serves
  each GNOME the newest version that lists it.
- A change to `shell-version` is a release: bump `version-name`, tag it, and the `release`
  workflow publishes it.
- The same change updates each place outside `docs/decisions/` that names a GNOME major.
  `tests/style/test_gnome_versions.py` fails until each names one `metadata.json` lists, and
  until each place that names one names every major it lists. A
  distribution named for that GNOME, as Ubuntu 26.04 is in the README's "What you need",
  changes with it; review checks that.

### Consequences

- Good: no one gets a version that was never run on their GNOME.
- Bad: on the day a GNOME major is released, Scroll Zoom stays off for anyone already
  running it until a version that lists it is approved.
- Bad: listing two majors means running the scenarios on both, on two machines.

### Checked by

`make test-shell` runs only on a GNOME Shell whose major `metadata.json` lists
(`tests/shell.py`), so a new major starts by listing it on a branch.
`tests/style/test_bundle.py` refuses an entry that is not a whole major, or that the date
says is not released yet, counted as the site's own analyzer counts it: from the first of
March or September. `tests/style/test_gnome_versions.py` refuses a page or tool that names a
major `metadata.json` does not list, and a place naming one that leaves out another it
lists. The rules lens
checks that a change to `shell-version` says in its description which GNOME Shell its
`make test-shell` passed on.

## Reversing it

To list a major without running the scenarios on it, list it: the test shell's gate only
keeps the scenarios from running on a major that is not listed, and review is what asks
for the run. The date check stays either way, since the site refuses future majors.
