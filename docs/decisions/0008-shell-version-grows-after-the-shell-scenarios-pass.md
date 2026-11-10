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
- Never list a development release or a future one. extensions.gnome.org forbids future
  versions, and a pass on a release candidate is not a pass on the release.
- A major stays listed while each change can still be tested on it: keep a machine, virtual
  machine, or toolbox on a major that a long-term release ships, as Ubuntu 26.04 ships
  GNOME 50. A change that cannot pass on an older major removes it. People still on that
  major keep the last approved version that lists it, because extensions.gnome.org serves
  each GNOME the newest version that lists it.
- A change to `shell-version` is a release: bump `version-name`, tag it, and the `release`
  workflow publishes it.

### Consequences

- Good: no one gets a version that was never run on their GNOME.
- Bad: on the day a GNOME major is released, Scroll Zoom stays off for anyone already
  running it until a version that lists it is approved.
- Bad: listing two majors means running the scenarios on both, on two machines.

### Checked by

`make test-shell` runs only on a GNOME Shell whose major `metadata.json` lists
(`tests/shell.py`), so a new major starts by listing it on a branch.
`tests/style/test_bundle.py` refuses an entry that is not a whole major. The rules lens
checks that a change to `shell-version` says in its description which GNOME Shell its
`make test-shell` passed on.

## Reversing it

Add majors without running the scenarios on them. Nothing but review stands in the way.
