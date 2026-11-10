---
name: deliver
description: Deliver a change to Scroll Zoom through its loop, from intent to a pull request ready to merge. The requirement first and red, the smallest code that turns it green, fresh reviewers under each lens at the head, fixes proven by a failing test first, and again until every lens is clean. Use for any change that ends in a pull request here, and to resume one.
---

# Deliver a change

You own one pull request from its intent to ready. You write the requirement and the code;
reviewers you spawn, who never saw your work, judge it; you fix what they prove; you stop
when each lens's latest review is clean, or when the owner must decide. The pull request is
the loop's memory: its description, its commits, and its review comments are all a new
session needs to pick it up.

Read `AGENTS.md` and `review/README.md` before the first step. Copy the steps below into your
task list and mark a step you skip `skip: <reason>`.

## Steps

1. **Say the goal.** In a sentence: what the change is for, who notices it, and the smallest
   change that meets it. A question that needs no change is answered, and the loop ends.
2. **Intent first.** Branch from an up-to-date main as `type/short-name`. Write the
   description from `.github/PULL_REQUEST_TEMPLATE.md`: the requirements it makes true, the
   ones it touches, and the done-when lines, before any code; and the Commit section, kept
   current as the change grows. Open the pull request as a draft early, so CI runs beside the
   work.
3. **Red.** When the change alters what Scroll Zoom must do, write or change its feature under
   `requirements/` and its steps under `tests/requirements/`. Run the scenarios (`make check`,
   or `make test-shell` for `@shell` ones) and watch the new ones fail for the reason the
   requirement gives: an assertion, never a typo or an undefined step. Commit the requirement
   alone.
4. **Spec review.** Spawn one fresh reviewer under the requirements lens on the requirement's
   commit, before any code: is it the right requirement, can it be tested, and does it leave
   out how it will be built? Post its review, and fix the spec until it has no blocking
   finding. Skip this step for a change that makes no requirement true.
5. **Green.** Write the smallest code that makes `make check` and `make test-shell` pass.
   Commit in small units that each pass, in an order that tells the story.
6. **Prove.** `make format`, `make check`, `make test-shell`, then push. When the change
   touches the extension, the test shell, its harness, or a `@shell` step, also run
   `make test-shell` twice at once, as a review round's reviewers do, and both must pass.
   Wait for CI's `check` and `intent` to pass. When a job fails, read its log first: a
   failure in code the change touches gets a commit; a flake gets one rerun, and a second
   identical failure is not one. After bringing main into the branch, reread the description
   against what came in: what it lists, the steps it gives, and the version it names.
7. **Review round.** `make pr-fetch PR=<n>`, then `make loop-brief`. For each lens it names,
   spawn a fresh `reviewer` agent (`.claude/agents/reviewer.md`), all at once, each with the
   brief below. Check each review it returns with `make check-review REVIEW=<file>`, and post
   it verbatim as a comment of its own.
8. **Fix.** For each blocking finding, rerun its evidence. When it reproduces, write the
   failing test first, then the fix, and push. A finding that shows a requirement wrong or
   missing changes the requirement in its own commit. When it does not reproduce, post the run
   that shows so; the next round's reviewer judges it. Record each finding in the
   description's Reviewed section, with the commit that answers it or why it stands. A note
   never starts a round: fold it into a push that answers a blocking finding when it is cheap,
   and otherwise open an issue for it and link it.
9. **Again.** Repeat steps 6 to 8 with fresh reviewers until each lens's latest review is
   clean at the head. A reviewer reviews what changed since the last review under its lens and
   what that change reaches. When one lens has found something three rounds in a row, stop and
   ask the owner to settle what is left, giving each side's evidence.
10. **Lessons.** For each confirmed finding: could a check have caught it? If so, add the check
    in the push that fixes it when it is small, or open an issue labelled `lesson`, and add the
    rule and its check to the table in `AGENTS.md`.
11. **Hand over.** Once every lens is clean and every check is green, mark the pull request
    ready and tell the owner. The owner merges it, squashed, under its title over its Commit
    section.

## The reviewer's brief

```text
Read .claude/agents/reviewer.md in full and follow it.

Pull request: #<number>, head <40-digit commit>
Lens: <rules | correctness | requirements>

<the output of make loop-brief, verbatim>

Earlier reviews under this lens: <none, or each one's text, oldest first>
Commits since the last of them: <none, or git log --oneline <its head>..<this head>>
```

Give the reviewer nothing else: not your plan, not your reasoning, not what you think is
wrong. A reviewer that knows what you meant checks what you meant to build.

## Never

- Edit a scenario to make it pass, or loosen a check without saying so in the description.
- Post a review you wrote, edited, or summarized. A review is the reviewer's text.
- Reuse a reviewer for a later round.
- Push to `main`, force push, bypass a hook, or merge.
