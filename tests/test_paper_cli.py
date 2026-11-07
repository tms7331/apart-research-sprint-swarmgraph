"""bin/build-paper's command line, on a copy of the real paper.typ with no data sources (no test reads a log):
the paper compiles, a draft lists its problems and exits 0, and --final refuses them and exits 1."""

import shutil
from pathlib import Path

import pytest

from paper.__main__ import main

PAPER = Path(__file__).resolve().parent.parent / "paper"


@pytest.fixture
def paper_dir(tmp_path):
    for name in ("paper.typ", "apart.typ", "lib.typ", "refs.bib", "citations.md"):
        shutil.copy(PAPER / name, tmp_path / name)
    return tmp_path


def test_a_draft_lists_its_problems_and_succeeds(paper_dir, capsys):
    assert main([], paper_dir, sources={}) == 0
    out = capsys.readouterr().out
    assert str(paper_dir / "build" / "DRAFT-paper.pdf") in out
    assert "missing: tb.solo.flagged: not in the ledger" in out
    assert "TODO" in out


def test_a_final_build_with_problems_fails_and_writes_nothing(paper_dir, capsys):
    # Its only link is a closed local port, so the link check makes no request beyond this machine.
    paper = '#import "lib.typ": *\n#show: apart.with(abstract: [x], sprint-url: "http://127.0.0.1:9/")\n'
    (paper_dir / "paper.typ").write_text(paper)
    assert main(["--final"], paper_dir, sources={}) == 1
    assert "nothing written" in capsys.readouterr().out
    assert not list(paper_dir.glob("*.pdf"))


def test_a_swallowed_semicolon_is_a_problem_and_unclaimed_wording_a_warning(paper_dir, capsys):
    paper = '#import "lib.typ": *\n#show: apart.with(abstract: [x])\nEvery model: #n("demo.a"); then more.\n'
    (paper_dir / "paper.typ").write_text(paper)
    assert main([], paper_dir, sources={}) == 0
    out = capsys.readouterr().out
    assert 'semicolon: line 3: #n("demo.a"); drops its' in out
    assert (
        "1 warning (neither a draft nor --final refuses them):\n  line 3: every, with no #claim after it"
        in out
    )


def test_a_hash_before_a_digit_is_a_problem(paper_dir, capsys):
    paper = '#import "lib.typ": *\n#show: apart.with(abstract: [x])\n= Methods\nSee (#39).\n'
    (paper_dir / "paper.typ").write_text(paper)
    assert main([], paper_dir, sources={}) == 0
    assert "hash: line 4: #39 renders as 39" in capsys.readouterr().out


def test_a_paper_typst_cannot_compile_fails_with_its_error(paper_dir, capsys):
    (paper_dir / "paper.typ").write_text('#import "lib.typ": *\n#nonsense\n')
    assert main([], paper_dir, sources={}) == 1
    assert "nonsense" in capsys.readouterr().err
