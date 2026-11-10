# SPDX-License-Identifier: GPL-2.0-or-later
"""The form a review takes, and the lenses a change needs."""

from tools.review import needed, problems

HEAD = "0123456789abcdef0123456789abcdef01234567"
CLEAN = f"""## Review: correctness

Head: {HEAD}
Verdict: clean

Done when:
1. met
2. out of scope: needs a real touchpad

Findings: none

What was reviewed and run.
"""

FINDINGS = f"""## Review: rules

Head: {HEAD}
Verdict: findings

Done when:
1. unmet: the README still says zoom jumps

Findings:
1. blocking: README.md line 20 says each notch jumps 20%
   Evidence: grep -n jumps README.md printed 20:each notch jumps 20%
2. note: a name could carry its unit
"""


def test_a_clean_review_is_well_formed() -> None:
    assert problems(CLEAN) == []


def test_a_review_with_findings_is_well_formed() -> None:
    assert problems(FINDINGS) == []


def test_an_unknown_lens_is_refused() -> None:
    assert any("no lens" in p for p in problems(CLEAN.replace("correctness", "vibes")))


def test_a_blocking_finding_needs_evidence() -> None:
    review = FINDINGS.replace(
        "   Evidence: grep -n jumps README.md printed 20:each notch jumps 20%\n", ""
    )
    assert any("Evidence" in p for p in problems(review))


def test_a_clean_verdict_with_an_unmet_line_is_refused() -> None:
    review = CLEAN.replace("1. met", "1. unmet: still blurry")
    assert any("verdict" in p for p in problems(review))


def test_done_when_must_be_numbered_in_order() -> None:
    review = CLEAN.replace("2. out of scope", "3. out of scope")
    assert any("numbered" in p for p in problems(review))


def test_documentation_alone_needs_only_the_rules_lens() -> None:
    assert needed(["README.md", "docs/decisions/0001-x.md"], names_requirements=False) == ["rules"]


def test_code_needs_correctness_and_a_feature_needs_requirements() -> None:
    paths = ["scroll-zoom@nhicc/smoothing.js", "requirements/SZ-004-x.feature"]
    assert needed(paths, names_requirements=False) == ["rules", "correctness", "requirements"]
