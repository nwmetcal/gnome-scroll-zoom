# Requirements run in a private headless shell

- Status: accepted
- Date: 2026-11-09
- Decided by: Nicholas Metcalf

## Context

Most of what Scroll Zoom must do happens inside GNOME Shell, which loads an extension's code
only at login on Wayland. A test that needs a logout cannot run in a loop.

## Options

- Test only the parts that run outside the shell, and the rest by hand.
- Run a private GNOME Shell for tests: headless, on its own D-Bus session, settings, and
  runtime folder, with the extension loaded.

## Decision

A private headless shell (`dev/test-shell.sh`), because it loads the extension under test at
start, feels input through virtual devices along the same path real input takes, and takes
screenshots, all without touching the desktop. A helper extension turns on the shell's unsafe
mode inside that shell only, so tests can run JavaScript in it.

### Consequences

- Good: the `@shell` scenarios run in under a minute, end to end, on the machine the
  extension is built on.
- Bad: they need GNOME Shell 50 and a GPU render node, which GitHub's runners lack, so CI
  leaves them pending and `make test-shell` runs on a developer's machine.

### Checked by

Every `@shell` scenario; collection in `tests/conftest.py` leaves them pending without
`--shell`.

## Reversing it

Delete `dev/test-shell.sh` and the `@shell` scenarios; the extension does not depend on it.
