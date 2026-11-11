# Reviewing a pull request

A review is one lens's independent judgment of one head commit and one intent. The reviewer
did not write the change, starts without its author's reasoning, and reads and runs the
change. Each lens is a file in `lenses/` that says what it looks for and when a change needs
it. `make loop-brief` names the lenses a change needs.

## What the reviewer is given

- The pull request's number and its head commit.
- The lens, and its file in `lenses/`.
- The brief `make loop-brief` prints: the head, the lenses, the paths changed, the Intent
  section, and the done-when lines, numbered.
- On a later round, the earlier reviews under this lens, and the commits since the last one.

Nothing else: not the author's notes, plan, or reasoning. The description, the diff, the
rules, and the decisions are what the change is judged against.

## What the reviewer does

1. Read `AGENTS.md`, the records in `docs/decisions/` the change touches or should, the
   description, and the diff against main: `git diff origin/main...HEAD`, all of it on a
   first round, and on a later round what changed since the last review's head and what that
   change reaches.
2. Run the change: `make check`, and `make test-shell` when the change touches the extension
   or a `@shell` scenario, plus whatever proves or disproves a finding. A claim is checked by
   a run, not by reading alone.
3. Hunt under the lens for what is wrong, and prove each finding against the head: a failing
   test, a script and what it printed, or the line of a document or rule the change made
   wrong. Keep scripts outside the repository. Never edit, commit, push, or comment.
4. Judge each done-when line: met, unmet, or out of scope, with why for the last two.
5. Write the review in the form below, check it with `make check-review REVIEW=<file>`, and
   hand it back. The author posts it, verbatim, as a comment of its own.

A later round is a fresh reviewer. It reruns each earlier blocking finding's evidence, which
must now show the fix, and reviews what changed since the last review under its lens and what
that change reaches. From the third review under a lens on, a finding outside what changed is
a note. Every done-when line is still judged for the whole change.

## What blocks

A finding blocks only when a run at the head shows it, or when the change made a line of a
document or rule wrong, and it breaks the intent, a rule in `AGENTS.md`, or a decision. A
done-when line the change does not meet blocks, in every round. Everything else is a note:
naming, structure, a style no formatter owns, a risk that needs a later change to matter. A
note never holds a change back and never starts a round: the author fixes it in a push that
answers a blocking finding when it is cheap and in scope, and otherwise opens an issue for it.

A frame-rate mark, such as SZ-003's view moving at least 120 times a second, can fail when many
test shells share a loaded machine, on main's code as on the head's. So a reviewer whose run
fails one reruns that scenario alone, once `pgrep -f 'gnome-shell --headless'` shows no other
test shell, at the head and on main's code, and reports it as blocking only when the head
fails alone and main passes alone.

## The form

```text
## Review: correctness

Head: <the 40-digit head commit, from the brief>
Verdict: findings

Done when:
1. met
2. unmet: a notch still jumps 20% in one frame
3. out of scope: needs a real touchpad

Findings:
1. blocking: zooming out past 1x leaves zoom on at 1x
   Evidence: `uv run pytest --shell tests/requirements/test_sz_001.py -k "all the way out"` failed: zoom on at 1.0x; SZ-001 says zoom is off
2. note: the glide's time constant could carry its unit in its name

A few short paragraphs: what was reviewed, what ran and what it printed, and what was not
checked, so the next reader knows what the review covers.
```

- The first line is `## Review: <lens>`, the lens as its file in `lenses/` is named.
- `Head:` is the head commit from the brief.
- `Verdict:` is `clean` when no finding blocks and no done-when line is unmet, and `findings`
  otherwise.
- `Done when:` judges every line of the brief, by its number, in order.
- `Findings:` numbers each finding `blocking:` or `note:`. A blocking one has an `Evidence:`
  line, indented three spaces: the command, what it printed, and what the intent or rule
  requires. A blocking finding on a frame-rate mark gives both runs alone: the head's, which
  failed, and main's, which passed. With nothing found, the line reads `Findings: none`.
