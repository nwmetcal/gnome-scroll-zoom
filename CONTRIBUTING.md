# Contributing to Scroll Zoom

Thanks for helping. Bug reports and ideas go in
[issues](https://github.com/nwmetcal/gnome-scroll-zoom/issues). For a bug, say your GNOME
version (`gnome-shell --version`), your display's size and refresh rate, and what
`journalctl --user -b -g scroll-zoom` prints.

## How changes are made

Changes follow the loop in [AGENTS.md](AGENTS.md), which holds every rule and what enforces
it:

1. Each behavior is a Gherkin requirement under `requirements/`, named by its `SZ-###` id.
   A change that alters behavior starts there, and its scenarios are seen to fail first.
2. Then the smallest code that makes them pass.
3. Then independent reviews, under the lenses in `review/lenses/`, until each is clean.

[docs/explanation/the-loop.md](docs/explanation/the-loop.md) says how the parts fit, and
`docs/decisions/` records why the design is what it is.

## Setting up

You need GNOME Shell 50, `uv`, `gjs`, and `make`.

```bash
make setup        # the Python tools, and the git hooks in .githooks/
make check        # lint, types, and every test that needs no GNOME Shell
make test-shell   # all of that, plus the scenarios that run in GNOME Shell 50
make install      # install your working copy; log out and back in to load it
```

`make test-shell` starts a private, headless GNOME Shell with the extension loaded
(`dev/test-shell.sh`). It runs on its own D-Bus session and settings, so it never touches
your desktop. It types and scrolls through virtual input devices and checks what GNOME
draws. It runs Wayland apps and, through Xwayland, X11 apps, as most games are.
Test shells with different roots (`TEST_SHELL_ROOT`), such as each `make test-shell` run's,
run side by side.

## Looking at the smoothing by eye

```bash
dev/test-shell.sh start
dev/test-shell.sh client gjs -m "$PWD/dev/test-page.js"
dev/capture.sh /tmp/shots 4 200 140     # zoom 4x on a point, screenshot each style
dev/montage.py /tmp/shots/cmp.png 0 120 1000 260 /tmp/shots/*-4x.png
dev/test-shell.sh stop
```

`dev/demo.py` makes the animation the README shows.

## Commits

Commit titles are `type(scope): description`, lowercase, at most 72 characters, with a
body of `-` bullets. The commit-msg hook checks them; `make check-commits` checks a branch.

## Releases

Push a tag `vX.Y.Z` matching `version-name` in `scroll-zoom@nhicc/metadata.json`. The
`release` workflow builds `scroll-zoom.shell-extension.zip` and publishes the release. Once
the extensions.gnome.org account is set, it then uploads the same bundle there for review,
and GNOME updates everyone who installed from there once it is approved
([decision 0007](docs/decisions/0007-updates-reach-people-through-extensions-gnome-org.md)).
`make zip` builds the same bundle locally, and `make check` holds it to the rules of the
site's review guidelines that a file check can see (`tests/style/test_bundle.py`).

The account is two settings in the repository's settings on GitHub: the variable
`EGO_USERNAME`, and the secret `EGO_PASSWORD` in the environment `extensions-gnome-org`.
Each upload makes, in the account's name, the two statements the site's upload page asks
for (`STATEMENTS` in `tools/ego.py`). Without the variable, a release uploads nothing.

## After a GNOME upgrade

`metadata.json` lists only the GNOME versions the tests have passed on
([decision 0008](docs/decisions/0008-shell-version-grows-after-the-shell-scenarios-pass.md)).
To add one, on a branch, add its major to `shell-version` and run `make test-shell` on a
machine whose `gnome-shell --version` reports it; the test shell refuses a major
`metadata.json` does not list. Fix what fails, merge once it passes on the stable release,
and release it. The same change updates each place that names a GNOME major, which
`tests/style/test_gnome_versions.py` finds, whether a major was added or dropped.
