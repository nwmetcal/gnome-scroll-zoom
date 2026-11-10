# Updates reach people through extensions.gnome.org

- Status: accepted
- Date: 2026-11-10
- Decided by: Nicholas Metcalf

## Context

People install Scroll Zoom from a release's zip or from a checkout, and neither updates
itself, so a fix reaches only those who reinstall. GNOME Shell 50 has an updater of its own:
at each login and once a day it asks extensions.gnome.org about every extension in the
person's own extensions folder, downloads a newer version that supports their GNOME, and
installs it at the next login (`ui/extensionDownloader.js` and `ui/extensionSystem.js` in
`libshell-18.so`). It asks by the `version` number extensions.gnome.org writes into each
bundle it serves, and a copy without one is skipped.

## Options

- Publish on extensions.gnome.org, and keep the release zip for people who install by hand.
- Have the extension check GitHub for releases and replace its own files.
- Package it for each distribution.

## Decision

Publish on extensions.gnome.org, because GNOME Shell then finds, downloads, and installs each
update itself, and every version is read by a reviewer before anyone gets it. An extension
that replaced its own files would run code nobody reviewed and would need the network, which
a zoom has no other use for. Packages wait on each distribution's own process.

A tag `vX.Y.Z` still publishes the release zip, and the `release` workflow then uploads that
same bundle to extensions.gnome.org, as `gnome-extensions upload` does, once the owner has
set the account's name and password (`EGO_USERNAME`, `EGO_PASSWORD`). Each upload makes two
statements in the owner's name: that GNOME may distribute the extension under GNOME Shell's
license, and that the site's staff may remove, modify, or reassign it. Without the account
set, the workflow uploads nothing.

### Consequences

- Good: once a version is approved, GNOME finds it at the person's next login or daily
  check, downloads it, and loads it at the login after that. At the first login after a
  GNOME upgrade, GNOME installs updates before it loads extensions.
- Good: people never need a terminal: Extension Manager or the website installs it.
- Bad: each version waits for a reviewer, for days or longer, and a reviewer may question
  the magnifier internals the extension reaches into (decision 0001).
- Bad: GNOME looks for updates only while the Extensions app or Extension Manager is
  installed and extension installs are allowed (`updatesSupported`). The README says so.
- Bad: the release zip and `make install` still never update themselves. The README says
  so, and how to switch.

### Checked by

`tests/style/test_bundle.py` holds the bundle to the review guidelines' rules a file check
can see. `tests/unit/test_ego.py` holds the upload to what `gnome-extensions upload` sends.

## Reversing it

Remove the `ego` job from the `release` workflow and `tools/ego.py`, and point the README
back at the release zip. Copies installed from extensions.gnome.org keep working. Marking the
extension inactive there stops new installs, and GNOME then finds no newer version for the
copies already installed.
