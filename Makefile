# SPDX-License-Identifier: GPL-2.0-or-later
UUID := scroll-zoom@nhicc
BASE ?= origin/main
HEAD ?= HEAD
PYTHON_DIRS := tests tools dev

.PHONY: setup check lint types test test-shell format check-commits check-intent pr-fetch \
	loop-brief check-review install zip clean

# The Python tools, and git's hooks from .githooks/.
setup:
	uv sync
	git config core.hooksPath .githooks

# Everything that needs no GNOME Shell. Writes build/traceability.md.
check: lint types test

lint:
	uv run ruff format --check $(PYTHON_DIRS)
	uv run ruff check $(PYTHON_DIRS)

types:
	uv run pyright

test:
	uv run pytest

# The same tests and the @shell scenarios, in a private headless GNOME Shell 50.
test-shell: lint types
	uv run pytest --shell

format:
	uv run ruff format $(PYTHON_DIRS)
	uv run ruff check --fix $(PYTHON_DIRS)

check-commits:
	python3 -m tools.commits --range $(BASE)..$(HEAD)

check-intent:
	@test -n "$(BODY)" || { echo "usage: make check-intent BODY=<file>" >&2; exit 2; }
	python3 -m tools.intent --body $(BODY) --base $(BASE)

pr-fetch:
	@test -n "$(PR)" || { echo "usage: make pr-fetch PR=<number>" >&2; exit 2; }
	mkdir -p build/pr
	gh pr view $(PR) --json body --jq .body > build/pr/body.md

loop-brief:
	python3 -m tools.review brief --body build/pr/body.md --base $(BASE)

check-review:
	@test -n "$(REVIEW)" || { echo "usage: make check-review REVIEW=<file>" >&2; exit 2; }
	python3 -m tools.review check $(REVIEW)

# For the current user; on Wayland, GNOME loads it at the next login.
install:
	./install.sh

# The bundle people download, for `gnome-extensions install`, which compiles its schema.
zip:
	mkdir -p build
	rm -f build/scroll-zoom.shell-extension.zip
	cd $(UUID) && zip -qrD ../build/scroll-zoom.shell-extension.zip . -x 'schemas/gschemas.compiled'
	@ls -l build/scroll-zoom.shell-extension.zip

clean:
	rm -rf build
