# Every change goes through the loop

- Status: accepted
- Date: 2026-11-09
- Decided by: Nicholas Metcalf

## Context

Scroll Zoom is built mostly by coding agents. An agent that reviews its own work checks what
it meant to build, not what it built.

## Options

- Review changes by hand.
- A loop: requirements as Gherkin features written first and red, the smallest code that
  turns them green, and fresh reviewer agents under separate lenses that prove each finding
  with a run, until every lens is clean.

## Decision

The loop, in `AGENTS.md` and the `deliver` skill, because it keeps the owner's attention for
judgments only, and leaves in the pull request everything a new session needs to pick it up.
The code that existed before the loop came in with requirements that describe it; the loop
applies to every change after.

### Consequences

- Good: every behavior has a scenario; every finding has a run behind it; every lesson
  becomes a check in the table in `AGENTS.md`.
- Bad: more steps per change; the review gate is followed by hand until it is automated.

### Checked by

`make check-intent`, `make check-review`, the commit rules, and the rules lens.

## Reversing it

Delete `.claude/skills/deliver/`, `.claude/agents/`, `review/`, and the loop's section of
`AGENTS.md`; the requirements and checks stand on their own.
