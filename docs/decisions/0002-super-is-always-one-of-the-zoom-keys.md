# Super is always one of the zoom keys

- Status: accepted
- Date: 2026-11-09
- Decided by: Nicholas Metcalf

## Context

On macOS, Control and scroll zooms the screen. On GNOME under Wayland, mutter sends a scroll
over a window straight to that window's app, before the shell sees it, unless the window-drag
key (`org.gnome.desktop.wm.preferences mouse-button-modifier`, Super by default) is held.

## Options

- Hold Super, alone or with Alt, Ctrl, or Shift.
- Ctrl and scroll, as macOS does, by grabbing input or by a daemon that reads input devices.

## Decision

Super, alone by default, because it is the only key the shell sees scrolls under without a
grab, and no app uses Super and scroll, while apps do use Ctrl and scroll to zoom their own
content.

### Consequences

- Good: no app loses a shortcut; no daemon or input permissions.
- Bad: someone who changes the window-drag key must pick zoom keys that include it.

### Checked by

SZ-001's scenarios hold Super through virtual devices, so they go through mutter's real
routing; one checks that another key held with Super leaves zoom alone.

## Reversing it

Ctrl and scroll would need an input grab in the shell or a privileged daemon, and would take
Ctrl and scroll from every app. Nothing here makes that cheaper; it is a new design.
