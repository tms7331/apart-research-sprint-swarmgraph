"""bin/build-slides: the video's slides, from the same data sources and figures as the paper.

Runs every data source into the ledger and draws the figures, exactly as bin/build-paper does, then compiles
paper/slides.typ (16:9) to paper/build/slides.pdf and a PNG of each slide in paper/build/slides/. A tweak to a
figure in paper/data/ shows in both the paper and the slides on their next build.
"""

import argparse
import json
import shutil
import sys
from pathlib import Path

import typst

from paper import FONTS
from paper.build import build_lock, fill, markdown, stamp, write_atomic, write_pages
from paper.data import registered
from paper.git import Repo

PAPER = Path(__file__).resolve().parent
PPI = 80  # the slide images: enough to check a layout


def build_slides(paper_dir: Path = PAPER) -> tuple[Path, list[Path], list]:
    """Fills the ledger and figures, then compiles slides.typ. Returns the PDF, the slide images and the data
    sources' problems (a failing source leaves its figures out, and their slides show a red marker)."""
    out, repo = paper_dir / "build", Repo.of(paper_dir)
    with build_lock(out):
        shutil.rmtree(out / "figures", ignore_errors=True)
        ledger, problems = fill(registered(), out / "figures", repo)
        out.mkdir(parents=True, exist_ok=True)
        (out / "numbers.json").write_text(json.dumps(ledger.entries, indent=1, ensure_ascii=False) + "\n")
        (out / "numbers.md").write_text(markdown(ledger.entries))
        compiler = typst.Compiler(paper_dir / "slides.typ", root=paper_dir, font_paths=[FONTS],
                                  ignore_system_fonts=True, sys_inputs={"stamp": stamp(repo)})
        pdf = compiler.compile(format="pdf")
        pngs = compiler.compile(format="png", ppi=PPI)
    path = out / "slides.pdf"
    write_atomic(path, pdf)
    return path, write_pages(out / "slides", pngs if isinstance(pngs, list) else [pngs]), problems


def main(argv: list[str] | None = None, paper_dir: Path = PAPER) -> int:
    parser = argparse.ArgumentParser(
        prog="build-slides",
        description="Build paper/slides.typ, the video's slides, from the same ledger and figures as the paper. "
        "Writes paper/build/slides.pdf and a PNG of each slide in paper/build/slides/.",
    )
    parser.parse_args(sys.argv[1:] if argv is None else argv)
    try:
        pdf, slides, problems = build_slides(paper_dir)
    except typst.TypstError as error:
        print(f"Typst couldn't compile slides.typ:\n{error}", file=sys.stderr)
        return 1
    print(f"{pdf.relative_to(Path.cwd()) if pdf.is_relative_to(Path.cwd()) else pdf}: {len(slides)} slides "
          f"(pictures in {slides[0].parent.name}/)" if slides else f"{pdf}: no slides")
    for problem in problems:
        print(f"  {problem.check}: {problem.detail}")
    return 0
