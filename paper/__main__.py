"""bin/build-paper: builds the paper's draft, or with --final the submission (paper/README.md)."""

import argparse
import sys
from collections.abc import Mapping
from pathlib import Path

from paper.build import FINAL_NAME, BuildError, Report, build
from paper.checks import ABSTRACT_WORDS, MAX_BYTES, PAGE_CAP
from paper.data import Source
from paper.watch import main as watch_main

PAPER = Path(__file__).resolve().parent
SHOWN_CHANGES = 12  # build/changes.md lists them all


def shown(path: Path) -> str:
    """`path` from the working directory when it is under it."""
    return str(path.relative_to(Path.cwd())) if path.is_relative_to(Path.cwd()) else str(path)


def status(report: Report, final: bool) -> str:
    """The block a build ends with: the paper's measures, what changed, its problems and its warnings."""
    low, high = ABSTRACT_WORDS
    folder = shown(report.pages[0].parent) if report.pages else "no pages"
    head = f"{shown(report.pdf)}: {len(report.pages)} pages" if report.pdf else "Final build refused"
    lines = [
        f"{head} (pictures of each page in {folder})",
        f"  pages before References  {report.body_pages} (cap {PAGE_CAP})",
        f"  abstract                 {report.abstract_words} words ({low}-{high})",
        f"  TODO markers             {report.todos}",
        f"  missing numbers          {len(report.missing)}",
        f"  failed claims            {len(report.failed_claims)}",
        f"  unreferenced figures     {len(report.unreferenced)}",
        f"  missing sections         {', '.join(report.missing_sections) or 'none'}",
        f"  PDF size                 {report.size / 1e6:.1f} MB (cap {MAX_BYTES / 1e6:.0f} MB)",
        f"  changed since last build {len(report.changed)}",
        *(f"    {change}" for change in report.changed[:SHOWN_CHANGES]),
        *(
            [f"    and {len(report.changed) - SHOWN_CHANGES} more, in build/changes.md"]
            if len(report.changed) > SHOWN_CHANGES
            else []
        ),
    ]
    if report.problems:
        verdict = "nothing written" if final else "a draft lists them; --final refuses them"
        lines += ["", f"{len(report.problems)} problems ({verdict}):"]
        lines += [f"  {problem.check}: {problem.detail}" for problem in report.problems]
    elif final and report.pdf:
        lines += ["", f"Wrote {shown(report.pdf)} and {FINAL_NAME}-numbers.json beside it. Commit both."]
    if report.warnings:
        count = f"{len(report.warnings)} warning{'' if len(report.warnings) == 1 else 's'}"
        lines += ["", f"{count} (neither a draft nor --final refuses them):"]
        lines += [f"  {warning}" for warning in report.warnings]
    return "\n".join(lines)


def main(
    argv: list[str] | None = None, paper_dir: Path = PAPER, sources: Mapping[str, Source] | None = None
) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if argv[:1] == ["watch"]:
        return watch_main(argv[1:], paper_dir)
    parser = argparse.ArgumentParser(
        prog="build-paper",
        description="Build paper/paper.typ: fill in its numbers, tables and figures from the logs, compile "
        "it, and check it against the sprint's rules. Writes paper/build/DRAFT-paper.pdf, a PNG of each page "
        "in paper/build/pages/, and the ledger in paper/build/numbers.json and numbers.md (paper/README.md). "
        "`build-paper watch` rebuilds the draft each time the repo's HEAD moves (`build-paper watch -h`).",
    )
    parser.add_argument(
        "--final",
        action="store_true",
        help="the submission: every check must pass, every link resolve, the tree be clean and the logs "
        f"pushed; only then writes the unmarked paper/{FINAL_NAME}.pdf and its ledger",
    )
    args = parser.parse_args(argv)
    try:
        report = build(paper_dir, sources, final=args.final)
    except BuildError as error:
        print(f"build-paper: Typst couldn't compile paper.typ:\n{error}", file=sys.stderr)
        return 1
    print(status(report, args.final))
    return 1 if args.final and report.problems else 0


if __name__ == "__main__":
    sys.exit(main())
