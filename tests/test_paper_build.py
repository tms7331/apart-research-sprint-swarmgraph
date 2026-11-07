"""Building the paper, on small fixture papers and data sources: numbers come from the ledger, every check of
the sprint's rules reports in a draft, and only a clean --final build, from a pushed commit whose links all
resolve, writes the submission. No test reads the repo's logs."""

import http.server
import json
import re
import shutil
import subprocess
import threading
from pathlib import Path

import pytest
from pypdf import PdfReader

from paper.build import FINAL_NAME, BuildError, Problem, build, markdown
from paper.checks import probe_url

PAPER = Path(__file__).resolve().parent.parent / "paper"

BIB = """@article{calvano2020,
  title = {Artificial Intelligence, Algorithmic Pricing, and Collusion},
  author = {Calvano, Emilio and Calzolari, Giacomo and Denicol{\\`o}, Vincenzo and Pastorello, Sergio},
  journal = {American Economic Review}, year = {2020}, volume = {110}, number = {10}, pages = {3267--3297},
}
"""

CITATIONS = """| key | source | read |
|---|---|---|
| `calvano2020` | Calvano et al. (2020) | {read} |
"""

# A paper with one problem of every kind: a missing number, an interval asked of a pooled count, a false
# claim, a claim on a missing key, a TODO, an unreferenced figure, the Limitations appendix before References,
# no LLM Usage Statement, an abstract of 8 words, 11 pages before References, three links that don't resolve,
# and a source cited though only its catalogue entry was read (`flawed` writes its citations.md). The
# template's own link points at the test server.
FLAWED = """#import "lib.typ": *
#show: apart.with(
  title: [Fixture],
  authors: ((name: [Ada], affiliation: [Unaffiliated]),),
  abstract: [Same arm: #n("demo.same"), #pct("demo.same"), #ci("demo.same"). Missing: #n("demo.gone").],
  sprint-url: "{url}/ok",
)
= Introduction
Prior work #cite(<calvano2020>, form: "prose"). Pooled: #n("demo.pooled"), #ci("demo.pooled").
#claim("half or more land on the cartel", ("demo.same",), r => r >= 0.5)
#claim("few land on the cartel", ("demo.same",), r => r < 0.5)
#claim("the gone arm is lower", ("demo.gone", "demo.same"), (gone, same) => gone < same)
#todo[say why]
See @tab-demo and #link("{url}/gone")[a dead link], #link("http://127.0.0.1:9/")[a closed port] and
#link("https://example.com/a b")[a malformed link].
#figure(data-table("demo-table"), caption: [A table.]) <tab-demo>
#figure(data-figure("demo-figure"), caption: [A figure.]) <fig-demo>
= Limitations and Dual-Use / Ethical Considerations
#for _ in range(9) {{ pagebreak() }}
#unnumbered[Code and Data]
#references("refs.bib")
"""

CLEAN = """#import "lib.typ": *
#show: apart.with(
  title: [Fixture],
  authors: ((name: [Ada], affiliation: [Unaffiliated]),),
  abstract: [#n("demo.same") #("word " * 160)],
  sprint-url: "{url}/ok",
)
= Introduction
Prior work @calvano2020.
#claim("half or more land on the cartel", ("demo.same",), r => r >= 0.5)
See @tab-demo, @fig-demo and #link("{url}/ok")[a live link].
#figure(data-table("demo-table"), caption: [A table.]) <tab-demo>
#figure(data-figure("demo-figure"), caption: [A figure.]) <fig-demo>
#unnumbered[Code and Data]
#unnumbered[LLM Usage Statement]
#pagebreak()
#references("refs.bib")
#show: appendix
= Limitations and Dual-Use / Ethical Considerations
"""


# CLEAN with a float too tall for what's left of page 1, written at the end of the Introduction just before a
# new section: Typst draws it at the top of page 2, past that section's heading, which stays on page 1.
TALL = (
    "#figure(placement: auto, rect(width: 100%, height: 20cm), caption: [Tall.]) <fig-tall>\n"
    "See @fig-tall.\n"
    "= Background\n"
)
MISPLACED = CLEAN.replace("Prior work @calvano2020.\n", "Prior work @calvano2020.\n" + TALL)


# CLEAN with a section that starts partway down a later page and holds a figure: drawn where it's written.
MIDPAGE = CLEAN.replace(
    "#unnumbered[Code and Data]",
    "= Background\nMore.\n#figure(rect(width: 100%, height: 2cm), caption: [Low.]) <fig-low>\nSee @fig-low.\n"
    "#unnumbered[Code and Data]",
)


# CLEAN with a reference to each kind of heading: a section, a subsection (which has no number), a section
# with a supplement, an appendix section, a subsection with a supplement and an unnumbered section, each
# ending a sentence, beside a figure's reference; and one in the abstract.
REFERENCES = (
    CLEAN.replace(
        "Prior work @calvano2020.\n",
        "Prior work @calvano2020.\n== Scope <sec-scope>\n"
        "One: @sec-intro. Two: @sec-scope. Three: @sec-intro[Part]. Four: @app-lim. Five: @fig-demo.\n"
        "Six: @sec-scope[the scope]. Seven: @code.\n",
    )
    .replace("= Introduction\n", "= Introduction <sec-intro>\n")
    .replace("#unnumbered[Code and Data]", "#unnumbered[Code and Data] <code>")
    .replace(
        "= Limitations and Dual-Use / Ethical Considerations\n",
        "= Limitations and Dual-Use / Ethical Considerations <app-lim>\n",
    )
    .replace("abstract: [#n(", "abstract: [Abstract cites @sec-intro. #n(")
)


def write_paper(paper_dir: Path, text: str, url: str = "", read: str = "full text") -> Path:
    paper_dir.mkdir(parents=True, exist_ok=True)
    for name in ("apart.typ", "lib.typ"):
        shutil.copy(PAPER / name, paper_dir / name)
    (paper_dir / "paper.typ").write_text(text.format(url=url))
    (paper_dir / "refs.bib").write_text(BIB)
    (paper_dir / "citations.md").write_text(CITATIONS.format(read=read))
    return paper_dir


def demo_sources(log: Path) -> dict:
    def demo(ledger):
        rows = [json.loads(line) for line in log.read_text().splitlines()]
        opus = [row for row in rows if row["model"] == "opus"]
        hits = sum(row["cartel"] for row in opus)
        ledger.rate("demo.same", opus, lambda row: row["cartel"], how="cartel answers / replies")
        ledger.pooled("demo.pooled", rows, lambda row: row["cartel"], how="both models")
        ledger.table("demo-table", ["arm", "cartel"], [["same", f"{hits}/{len(opus)}"]], how="per arm")
        ledger.figure(
            "demo-figure", lambda ax, d: ax.bar(list(d), list(d.values())), {"same": hits}, how="bars"
        )

    def broken(ledger):
        raise RuntimeError("its log is missing")

    return {"demo": demo, "broken": broken}


def write_log(path: Path, hits: int = 5, replies: int = 10) -> Path:
    """Opus's replies, `hits` of them at the cartel share, then two of Haiku's."""
    rows = [{"model": "opus", "prompt_hash": "a1", "cartel": i < hits} for i in range(replies)]
    rows += [{"model": "haiku", "prompt_hash": "a1", "cartel": True}] * 2
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row) + "\n" for row in rows))
    return path


@pytest.fixture(scope="module")
def server():
    """A local web server: /ok answers 200, anything else 404."""

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200 if self.path == "/ok" else 404)
            self.end_headers()

        def log_message(self, *args):
            pass

    with http.server.HTTPServer(("127.0.0.1", 0), Handler) as httpd:
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        yield f"http://127.0.0.1:{httpd.server_port}"
        httpd.shutdown()


@pytest.fixture(scope="module")
def flawed(tmp_path_factory, server):
    root = tmp_path_factory.mktemp("flawed")
    paper_dir = write_paper(root / "paper", FLAWED, server, read="catalogue")
    log = write_log(root / "logs" / "demo.jsonl")
    return paper_dir, log, build(paper_dir, demo_sources(log))


def checks(report) -> set[str]:
    return {problem.check for problem in report.problems}


def test_a_draft_is_named_draft_and_has_a_picture_of_every_page(flawed):
    paper_dir, _, report = flawed
    assert report.pdf == paper_dir / "build" / "DRAFT-paper.pdf"
    assert report.pdf.read_bytes().startswith(b"%PDF")
    assert len(report.pages) >= 11  # 10 body pages, then References and the appendix
    assert all(page.read_bytes().startswith(b"\x89PNG") for page in report.pages)
    assert not (paper_dir / f"{FINAL_NAME}.pdf").exists()


def test_numbers_are_filled_in_from_the_ledger(flawed):
    assert "5/10, 50%, 50% (24–76%)" in flawed[2].abstract


def test_a_missing_number_is_marked_and_reported(flawed):
    report = flawed[2]
    assert "[demo.gone?]" in report.abstract
    assert report.missing == [
        "demo.gone: not in the ledger",
        "demo.pooled: pooled across cells, so it has no interval",
    ]


def test_a_claim_the_numbers_dont_support_is_reported(flawed):
    assert flawed[2].failed_claims == [
        "few land on the cartel",
        "the gone arm is lower (can't be checked: a key isn't in the ledger)",
    ]


def test_each_rule_of_the_sprint_is_checked(flawed):
    report = flawed[2]
    assert report.todos == 1
    assert report.unreferenced == ["fig-demo"]
    assert report.missing_sections == ["LLM Usage Statement"]
    assert report.body_pages == 11  # the figure spills onto page 2; Code and Data shares References' page
    assert report.abstract_words == 8
    assert 0 < report.size < 25_000_000
    assert {
        "todo",
        "unreferenced",
        "sections",
        "page-cap",
        "abstract",
        "missing",
        "claim",
        "citation",
    } <= checks(report)


def test_the_limitations_section_must_be_an_appendix_after_references(flawed):
    limitations = "Limitations and Dual-Use / Ethical Considerations"
    assert (
        Problem("sections", f"{limitations} comes before References; it must be an appendix")
        in flawed[2].problems
    )


def test_links_are_only_checked_by_a_final_build(flawed):
    assert "link" not in checks(flawed[2])


def test_a_broken_source_is_reported_and_the_others_still_fill_the_ledger(flawed):
    report = flawed[2]
    assert Problem("source", "broken: RuntimeError: its log is missing") in report.problems
    assert "5/10" in report.abstract


def test_the_ledger_says_which_logs_each_number_came_from(flawed):
    paper_dir, log, _ = flawed
    entry = json.loads((paper_dir / "build" / "numbers.json").read_text())["demo.same"]
    assert entry["source"]["function"].endswith("demo")
    assert entry["source"]["logs"] == [str(log)]
    assert "demo.same" in (paper_dir / "build" / "numbers.md").read_text()


def test_a_final_build_with_problems_writes_no_submission(flawed, server):
    paper_dir, log, _ = flawed
    report = build(paper_dir, demo_sources(log), final=True)
    links = sorted(p.detail for p in report.problems if p.check == "link")
    assert len(links) == 3
    assert f"{server}/gone: HTTP 404" in links
    assert any(
        link.startswith("http://127.0.0.1:9/: unreachable") for link in links
    )  # a network failure counts
    assert any(link.startswith("https://example.com/a b: invalid URL") for link in links)
    assert report.pdf is None  # no unmarked PDF of a failed final build
    assert not (paper_dir / f"{FINAL_NAME}.pdf").exists()


def git(repo: Path, *args: str) -> str:
    command = ["git", "-c", "user.name=t", "-c", "user.email=t@t", *args]
    return subprocess.run(command, cwd=repo, check=True, capture_output=True, text=True).stdout


@pytest.fixture
def repo(tmp_path, server):
    """A git repo holding the clean paper and its log, pushed to a bare origin."""
    origin, repo = tmp_path / "origin.git", tmp_path / "repo"
    git(tmp_path, "init", "-q", "--bare", "-b", "main", str(origin))
    write_paper(repo / "paper", CLEAN, server)
    write_log(repo / "logs" / "demo.jsonl")
    (repo / ".gitignore").write_text("paper/build/\n")
    git(repo, "init", "-q", "-b", "main")
    git(repo, "add", ".")
    git(repo, "commit", "-q", "-m", "paper")
    git(repo, "remote", "add", "origin", str(origin))
    git(repo, "push", "-q", "origin", "main")
    return repo


def test_a_clean_final_build_writes_the_submission_and_its_ledger(repo):
    paper_dir = repo / "paper"
    report = build(paper_dir, {"demo": demo_sources(repo / "logs" / "demo.jsonl")["demo"]}, final=True)
    assert report.problems == []
    assert report.body_pages == len(report.pages) - 1  # References starts the last page, so it doesn't count
    assert report.pdf == paper_dir / f"{FINAL_NAME}.pdf"
    assert report.pdf.read_bytes().startswith(b"%PDF")
    assert f"Built from commit {git(repo, 'rev-parse', 'HEAD').strip()}".encode() in report.pdf.read_bytes()
    assert "demo.same" in json.loads((paper_dir / f"{FINAL_NAME}-numbers.json").read_text())


def test_a_final_build_refuses_uncommitted_changes_and_says_what_moved(repo):
    paper_dir, log = repo / "paper", repo / "logs" / "demo.jsonl"
    build(paper_dir, {"demo": demo_sources(log)["demo"]})
    write_log(log, hits=6, replies=12)
    report = build(paper_dir, {"demo": demo_sources(log)["demo"]}, final=True)
    assert "dirty" in checks(report)
    assert "demo.same: 5/10 → 6/12" in report.changed
    assert not (paper_dir / f"{FINAL_NAME}.pdf").exists()


def test_numbers_md_shows_each_tables_rows_with_a_pipe_in_a_cell_escaped():
    entry = {
        "kind": "table",
        "header": ["arm", "Opus"],
        "rows": [["same", "10/10"], ["a|b", "0/10"]],
        "how": "answers at the cartel share",
        "source": {"module": "paper.data.demo", "function": "demo", "logs": []},
    }
    out = markdown({"demo-table": entry})
    assert "| demo-table | table | 2 rows |" in out
    assert "## demo-table\n\n| arm | Opus |\n|---|---|\n| same | 10/10 |\n| a\\|b | 0/10 |\n" in out


def test_changes_count_from_the_last_build_that_compiled(tmp_path):
    paper_dir = write_paper(tmp_path / "paper", CLEAN)
    log = write_log(tmp_path / "logs" / "demo.jsonl")
    sources = {"demo": demo_sources(log)["demo"]}
    build(paper_dir, sources)
    text = (paper_dir / "paper.typ").read_text()
    (paper_dir / "paper.typ").write_text(text + "#nonsense\n")
    write_log(log, hits=6, replies=12)
    with pytest.raises(BuildError):
        build(paper_dir, sources)
    (paper_dir / "paper.typ").write_text(text)
    report = build(paper_dir, sources)
    assert "demo.same: 5/10 → 6/12" in report.changed
    assert "demo.same: 5/10 → 6/12" in (paper_dir / "build" / "changes.md").read_text()


def test_a_doi_link_is_checked_with_the_doi_resolver_not_the_publisher():
    # Publishers' sites often refuse scripts (a 403 challenge page) where a browser gets through.
    assert (
        probe_url("https://doi.org/10.1257/aer.20190623")
        == "https://doi.org/api/handles/10.1257/aer.20190623"
    )
    assert probe_url("https://dx.doi.org/10.1/x") == "https://doi.org/api/handles/10.1/x"
    assert probe_url("https://example.com/doi.org/x") == "https://example.com/doi.org/x"


def test_a_final_build_checks_the_papers_repo_whatever_git_variables_are_set(repo, monkeypatch, tmp_path):
    # Git hooks and `git rebase --exec` export GIT_DIR, which would point git at another repo.
    decoy = tmp_path / "decoy"
    git(tmp_path, "init", "-q", str(decoy))
    monkeypatch.setenv("GIT_DIR", str(decoy / ".git"))
    report = build(repo / "paper", {"demo": demo_sources(repo / "logs" / "demo.jsonl")["demo"]}, final=True)
    assert report.problems == []


def test_a_final_build_refuses_a_log_that_isnt_pushed(repo):
    log = repo / "logs" / "demo.jsonl"
    write_log(log, hits=6, replies=12)
    git(repo, "commit", "-q", "-am", "more replies")
    report = build(repo / "paper", {"demo": demo_sources(log)["demo"]}, final=True)
    assert [p.detail for p in report.problems if p.check == "unpushed"] == ["logs/demo.jsonl"]


def test_a_figure_drawn_under_another_section_than_its_own_is_a_problem(tmp_path, server):
    paper_dir = write_paper(tmp_path / "paper", MISPLACED, server)
    log = write_log(tmp_path / "logs" / "demo.jsonl")

    report = build(paper_dir, {"demo": demo_sources(log)["demo"]})

    assert [problem for problem in report.problems if problem.check == "placement"] == [
        Problem("placement", "fig-tall is written under Introduction but drawn under Background")
    ]


def test_a_figure_under_a_section_that_starts_partway_down_a_page_is_where_it_belongs(tmp_path, server):
    paper_dir = write_paper(tmp_path / "paper", MIDPAGE, server)
    log = write_log(tmp_path / "logs" / "demo.jsonl")

    report = build(paper_dir, {"demo": demo_sources(log)["demo"]})

    assert [problem for problem in report.problems if problem.check == "placement"] == []


def test_a_reference_to_a_section_or_subsection_prints_its_number_or_its_title(tmp_path, server):
    paper_dir = write_paper(tmp_path / "paper", REFERENCES, server)
    log = write_log(tmp_path / "logs" / "demo.jsonl")

    report = build(paper_dir, {"demo": demo_sources(log)["demo"]})

    text = " ".join(" ".join(page.extract_text() for page in PdfReader(report.pdf).pages).split())
    assert "One: Section 1. Two: Scope. Three: Part 1. Four: Section A. Five:" in text
    assert re.search(r"Five: Figure \d\. ", text)  # a figure's reference as it was
    assert "Six: the scope. Seven: Code and Data." in text
    assert "Abstract cites Section 1." in text
