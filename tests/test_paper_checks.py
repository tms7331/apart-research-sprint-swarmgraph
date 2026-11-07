"""The checks bin/build-paper runs on paper.typ's source: a semicolon Typst swallows after a call, a `#` it
swallows before a digit, and wording that rests on the numbers with no #claim behind it."""

from paper.checks import (
    Problem,
    swallowed_hashes,
    swallowed_semicolons,
    unclaimed_wording,
)

FIX = 'drops its ";" (write \\; to keep it)'

SOURCE = """= Results
GLM goes from #n("a") to #n("b"); Opus mentions antitrust in #n("c").
#claim("up", ("a", "b"), (x, y) => x < y);
// a comment about #n("d"); left alone
A sentence ends #n("e"). Another escapes it #n("f")\\; fine.
To do: #todo[say why]; then #link("https://x.org/a")[a link]; and a dash #sym.dash; here.
Deep: #claim("d", ("a",), r => calc.max(r, (1)) > 0); a trailing note // #n("g"); not code
"""


def test_a_semicolon_right_after_a_call_is_a_problem_naming_its_line():
    assert swallowed_semicolons(SOURCE) == [
        Problem("semicolon", f'line 2: #n("b"); {FIX}'),
        Problem("semicolon", f'line 3: #claim("up", ("a", "b"), (x, y) => x < y); {FIX}'),
        Problem("semicolon", f"line 6: #todo[say why]; {FIX}"),
        Problem("semicolon", f'line 6: #link("https://x.org/a")[a link]; {FIX}'),
        Problem("semicolon", f"line 6: #sym.dash; {FIX}"),
        Problem("semicolon", f'line 7: #claim("d", ("a",), r => calc.max(r, (1)) > 0); {FIX}'),
    ]


WORDING = """Every model reaches it in #n("a").
#claim("every model", ("a",), r => r == 1)
Nearly all answers are at 48 (#n("b")), and none at 36.
Every model agrees, with no number cited.

The strongest lever is the record, #pct("c").
The answers rose from #n("d") to #n("e"), mostly at 30.

Lockstep raises it to #n("f").
And lowers the mentions to #n("g").
#claim("lockstep", ("f", "g"), (f, g) => f > g)
// Every comment is skipped, #n("h").
A key's words don't count: #n("only.most.every"), nor quoted "all" words, nor number-only arms #n("i").
Neither firm deviates at #n("j"). // every trailing comment is skipped

#claim("neither", ("j",), r => r == 0)
"""


def test_wording_that_rests_on_cited_numbers_needs_a_claim_later_in_its_paragraph():
    assert unclaimed_wording(WORDING) == [
        "line 3: all, nearly, none, with no #claim after it",
        "line 6: strongest, with no #claim after it",
        "line 7: mostly, rose, with no #claim after it",
        "line 14: neither, with no #claim after it",  # the claim after a blank line is another paragraph's
    ]


HASHES = """The compliance criterion's results (#39).
Escaped (\\#40), quoted #n("key#41"), raw `#42`, and a color #text(fill: rgb("#c00000"))[red].
// A comment names #43.
Two on a line: #7 and #8.
"""


def test_a_hash_before_a_digit_is_a_problem_naming_its_line():
    assert swallowed_hashes(HASHES) == [
        Problem("hash", "line 1: #39 renders as 39 (write \\#39)"),
        Problem("hash", "line 4: #7 renders as 7 (write \\#7)"),
        Problem("hash", "line 4: #8 renders as 8 (write \\#8)"),
    ]
