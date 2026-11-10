# The rules lens

Does the change do what its Intent section says, follow the repository's rules, and leave
every document true? Every pull request needs this lens.

- **Intent.** Each done-when line is met by what the diff does, and the diff does nothing the
  intent does not cover. A pull request changes one behavior; one that changes two is a
  blocking finding that names them.
- **Rules.** The boundaries, the requirement rules, and the style rules in `AGENTS.md` that no
  linter checks: comments that say why, errors that propagate, units in names, the SPDX
  header. The commit messages pass `make check-commits`.
- **Decisions.** The change respects each record in `docs/decisions/` it touches. A choice
  that would be costly to undo has a record of its own, saying what undoing it takes.
- **Documents.** A line the change makes wrong, in `README.md`, `AGENTS.md`, `docs/`,
  `review/`, the agent files, or the settings window's text, is a blocking finding that
  quotes the line.
- **Enforcement.** A rule the change adds names what enforces it in the table in `AGENTS.md`,
  or says that review does.
- **Lessons.** When a finding belongs to a class a check could catch, a note names the check.
