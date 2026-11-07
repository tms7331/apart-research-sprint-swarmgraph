"""The paper's code names its figures by label or by what they show, never by number: a new figure or a moved
section renumbers them, and a comment that names a figure by its number goes stale with no check to notice."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NUMBERED = re.compile(r"\bFigure \d")


def test_the_papers_code_names_figures_by_label_not_number():
    files = [*ROOT.glob("paper/*.py"), *ROOT.glob("paper/data/*.py"), *ROOT.glob("tests/test_paper_*.py")]
    found = [
        f"{path.relative_to(ROOT)}:{number}"
        for path in files
        for number, line in enumerate(path.read_text().splitlines(), 1)
        if NUMBERED.search(line)
    ]
    assert found == []
