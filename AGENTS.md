# AGENTS.md

The rules for working on Scroll Zoom, for coding agents and people alike. Why they are what
they are is in `docs/decisions/` and `docs/explanation/the-loop.md`.

## Commands

- `make setup` installs the Python tools with uv and points git at the hooks in `.githooks/`.
- `make check` is the whole check that needs no GNOME Shell: lint (ruff, shellcheck), strict
  types (pyright), every scenario not tagged `@shell`, and the unit and style tests. It writes
  the traceability matrix to `build/traceability.md`. Nothing merges without it green.
- `make test-shell` runs `make check`'s tests and the `@shell` scenarios too, in a private
  headless GNOME Shell that `dev/test-shell.sh` starts (decision 0005). It needs a GNOME Shell
  whose major `metadata.json` lists, today GNOME Shell 50, and a GPU render node. Run it before pushing
  any change to the extension, and say in the pull request that it passed, and on which.
- `make format` rewrites the Python, which ruff owns.
- `make check-commits` checks the commit messages from `origin/main` to the branch's head.
- `make check-intent BODY=<file>` checks a description's Intent section against the branch.
- `make pr-fetch PR=<n>` saves a pull request's description to `build/pr/body.md`.
  `make loop-brief` prints what a reviewer is given for it, and
  `make check-review REVIEW=<file>` checks a review's form before it is posted.
- `make install` installs the working copy for the current user; on Wayland it loads at the
  next login. `make zip` builds `build/scroll-zoom.shell-extension.zip`, the bundle people
  download and install with `gnome-extensions install`, and the one extensions.gnome.org takes.
- A tag `vX.Y.Z` that matches `version-name` in `metadata.json` publishes a release with that
  bundle, through the `release` workflow, and once the owner has set the account, uploads it
  to extensions.gnome.org for review (decision 0008). A change under `site/` or to the
  README's images republishes the project page, through the `pages` workflow.

## Code map

- `scroll-zoom@nhicc/` is the extension. `extension.js` reads the scroll keys and the wheel,
  runs the glide each frame, and moves the view with the pointer. `zoomMotion.js` is the glide
  physics and imports nothing of GNOME Shell. `smoothing.js` is the shader that redraws the
  zoomed view. `prefs.js` is the settings window; `schemas/` its settings.
- `requirements/` holds the features. `tests/` holds their steps, in `tests/requirements/`,
  and the rest of the tests, in `tests/unit/` and `tests/style/`; `tests/shell.py` and
  `tests/shell_harness.js` drive the test shell, and `tests/full_screen_app.js` is the
  full-screen app SZ-008 zooms over.
- `dev/` holds the private test shell, the test window, and the capture tools for comparing
  smoothing by eye.
- `tools/` holds the repository's own tools: the commit rules, the intent check, the review
  brief and form check, and the upload to extensions.gnome.org. `review/` holds the review
  protocol and its lenses.
- `.claude/` holds the agent settings, the reviewer agent, and the `deliver` playbook.
  `.githooks/` holds the commit and push hooks, `.github/` the pull request template and the
  workflows.
- `docs/` holds the decisions, in `docs/decisions/`, how the loop works, in
  `docs/explanation/`, and the images the README and the project page show. `dev/demo.py`
  makes the animation.
- `site/` holds the project page, published at https://nwmetcal.github.io/gnome-scroll-zoom/.
  `README.md` is for people who use Scroll Zoom; `CONTRIBUTING.md` for people who work on it.

## Boundaries

- The extension drives GNOME's own magnifier and never draws a zoom without it (decision
  0001). Turned off, it hands zoom back to GNOME exactly as it found it.
- The only settings outside its own schema that it writes are GNOME's zoom on/off and zoom
  level, `screen-magnifier-enabled` and `mag-factor`.
- `zoomMotion.js` imports nothing of GNOME Shell, so the glide is tested without one.
- `metadata.json` lists only the GNOME Shell versions the `@shell` scenarios have passed on:
  a major joins once they pass on its stable release (decision 0009).
- The bundle is one extensions.gnome.org's review takes: only the files the extension loads,
  and a `disable()` that undoes everything `enable()` did.
- No tracked file is over 1 MB.
- Scroll Zoom is an accessibility tool, and its pages are for people with low vision: every
  image has alt text that says what it shows, an animation plays once and has a still for
  reduced motion, text reflows at 400% zoom, and nothing depends on color or a pointer alone.

## Requirements

- A requirement is a Gherkin feature under `requirements/`, named and titled by its `SZ-###`
  id, tagged one of `@invariant` (holds on every change) and `@golden` (compares what is drawn
  with a known answer), and `@shell` when a scenario needs GNOME Shell. Its steps are in
  `tests/requirements/test_sz_###.py`. Ids from `SZ-900` to `SZ-999` are kept for examples.
- Steps observe what a person would: GNOME's zoom state, the frames drawn, screenshots. Input
  goes in through virtual devices, the same path a real keyboard, mouse, and touchpad take. A
  step never asserts on the extension's internals.
- A figure in a scenario carries its unit: ms, Hz, percent, pixels, or x for a zoom factor.
- A scenario is never edited to make it pass. The code changes, or the requirement changes in
  a commit of its own, saying why.
- Tests come before code. A requirement a change makes true fails on main's code first.

## Style

- JavaScript is GJS ES modules in GNOME Shell's style: four spaces, single quotes,
  semicolons, `const` by default.
- Python 3.12 or later, ruff format and lint, pyright strict, line length 100. Type hints
  everywhere. No `Any`.
- Errors propagate with their cause. No blanket `catch` or `except`, no silent default.
- A number whose unit is not obvious carries it in its name: `delay_ms`, `rate_hz`.
- Comments say why, never what.
- No words that sell instead of saying, no tool or model names, no emoji.
- A shell script passes shellcheck.
- Every source file starts with `SPDX-License-Identifier: GPL-2.0-or-later`.

## The loop

Every change runs the loop. Its playbook is the `deliver` skill, in
`.claude/skills/deliver/SKILL.md`.

1. **Intent.** Branch, write the description's Intent section, and open a draft pull request.
2. **Red.** Write or change the requirement and watch its scenarios fail for the reason it
   gives. Commit it alone. A fresh reviewer under the requirements lens reviews it before any
   code is written.
3. **Green.** Write the smallest code that makes `make check` and `make test-shell` pass.
4. **Review.** `make loop-brief` names the lenses the change needs. A fresh reviewer agent
   reviews it under each, given only the brief and these rules (`.claude/agents/reviewer.md`,
   `review/README.md`). Each review is posted verbatim as a comment.
5. **Fix.** Rerun each blocking finding's evidence, fix it with a failing test first, and
   record in the description what changed because of it. A note never starts a round.
6. **Again.** Fresh reviewers review the new head until each lens's latest review is clean.
   When one lens has found something three rounds in a row, the owner settles what is left.
7. **Lessons.** A finding a check could have caught becomes that check, and joins the table
   below.

## Commits and pull requests

- Every change is a branch, a pull request, and a squash merge once its checks are green and
  each lens's latest review is clean. Never push to `main`, never force push, never bypass a
  hook.
- Title `type(scope): description`, imperative, lowercase, no period, at most 72 characters.
  A blank line, then a body of `-` bullets wrapped at 72: what changed and why. Plain text.
- No attribution trailers and no tool names in a commit, and no mention of how the change was
  written.
- A pull request changes one behavior. Its description starts with its Intent: the
  requirements it makes true, the ones it touches, and when it is done, written before the
  code. Then its Commit section, the bullets the squashed commit keeps as its body; then why,
  how it was verified, and what the reviews found and what changed because of each.

## Rules and what enforces them

| Rule | Enforced by |
| --- | --- |
| A feature is named and titled by its id, carries one kind tag, and has a steps module named for its id | collection in `tests/conftest.py`; `tests/style/test_traceability.py` |
| No two features share an id | `tests/style/test_traceability.py` |
| A scenario that needs GNOME Shell is tagged `@shell`, and is pending without the test shell | collection in `tests/conftest.py`; a step that needs the shell fails outside it |
| The glide runs without GNOME Shell | `tests/requirements/test_sz_002.py`, which loads `zoomMotion.js` in plain gjs |
| A description states its intent and declares every requirement the branch touches | `make check-intent`; the `intent` workflow |
| A review is well formed, and a blocking finding carries its evidence | `make check-review` |
| Commit messages follow the rules | the commit-msg hook; `make check-commits` in CI |
| Nothing reaches `main` but a merged pull request; no force push; no bypassed hook | the pre-push hook; the agent settings in `.claude/settings.json` |
| Every `make` target this file names exists, and the code map names every folder | `tests/style/test_agents_md.py` |
| No words that sell, no tool or model names, no emoji | `tests/style/test_words.py` |
| No tracked file over 1 MB | `tests/style/test_sizes.py` |
| The bundle holds only what the extension loads, metadata and a schema the site takes, and each process's own libraries; every signal, main loop source, and keybinding is undone | `tests/style/test_bundle.py` |
| `shell-version` lists only whole majors released by the date, counted as the site's analyzer counts them, and the test shell runs only on one it lists | `tests/style/test_bundle.py`; `gnome_shell_refusal` in `tests/shell.py` |
| Each GNOME major a page or tool names, outside the decisions, is one `metadata.json` lists, and each line saying which GNOME Scroll Zoom needs names every major it lists | `tests/style/test_gnome_versions.py` |
| A distribution named for a GNOME major changes with it | review: the rules lens |
| A change to `shell-version` says in its description which GNOME Shell its `make test-shell` passed on | review: the rules lens |
| An upload to extensions.gnome.org sends what `gnome-extensions upload` sends, and never prints the password or token | `tests/unit/test_ego.py` |
| A step crops only boxes wholly on its screenshot, so it never judges an empty crop | `crop` in `tests/images.py`, held by `tests/unit/test_images.py` |
| The `@shell` scenarios pass with test shells side by side, as a review round runs them | the `deliver` skill's Prove step: two `make test-shell` runs at once when the extension, the test shell, its harness, or a `@shell` step changes |
| Every image in the README and the project page has alt text | `tests/style/test_pages.py` |
| A release's tag matches the extension's `version-name` | the `release` workflow |
| The pages work for low vision: animation once with a still, reflow at 400%, nothing by color alone | review: the rules lens |
| A shell script passes shellcheck | `tests/style/test_shell.py` |
| No `Any`; a function's types are complete | ruff (`ANN`, `TID251`) and pyright strict, in `make check` |
| Steps observe what a person would, never internals; a requirement made true failed on main first; a scenario is never edited to pass; one behavior a pull request; comments say why; errors propagate | review: the requirements and rules lenses |
| The extension hands zoom back to GNOME when turned off, and writes no setting but its own and GNOME's zoom on/off and level | SZ-006; review: the correctness lens |
