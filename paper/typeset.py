"""Typst: compiles paper.typ to a PDF and page images, and reads back what the checks need (the abstract,
headings, figures and references, links, and the markers paper/lib.typ leaves) by querying the document."""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import typst

from paper import FONTS

PPI = 100  # the page images: enough to read a table, small enough to look at every page


class BuildError(RuntimeError):
    """Typst couldn't compile the paper."""


@dataclass(frozen=True)
class Typeset:
    pdf: bytes
    pngs: list[bytes]
    warnings: list[str]
    abstract: str
    missing: list[str]  # "key: why", for each number, table, figure or text the ledger couldn't supply
    claims: list[tuple[bool | None, str]]  # whether each claim holds (None: a key is missing), and its text
    todos: int
    references: tuple[int, float] | None  # the page and height (pt) just before the References heading
    figures: list[str]  # each figure's label, or its caption when it has none
    refs: set[str]  # the labels referenced
    cites: set[str]  # the bibliography keys cited, by @key or #cite
    headings: list[str]
    links: list[str]
    misplaced: list[tuple[str, str, str]]  # each figure drawn under another section: name, written, drawn


def plain(node: Any) -> str:
    """The text of a queried piece of content."""
    if isinstance(node, list):
        return "".join(plain(child) for child in node)
    if not isinstance(node, dict) or node.get("func") == "metadata":
        return ""
    if node.get("func") in ("space", "linebreak", "parbreak"):
        return " "
    if node.get("func") == "smartquote":
        return '"' if node.get("double") else "'"
    return (
        node.get("text", "")
        + plain(node.get("children", []))
        + plain(node.get("body"))
        + plain(node.get("child"))
    )


def paper_compiler(paper_dir: Path, inputs: dict[str, str]) -> typst.Compiler:
    """Typst for <paper_dir>/paper.typ with `inputs` as sys.inputs. The paper reads only inside paper_dir."""
    return typst.Compiler(
        paper_dir / "paper.typ",
        root=paper_dir,
        font_paths=[FONTS],
        ignore_system_fonts=True,
        sys_inputs=inputs,
    )


def typeset(paper_dir: Path, inputs: dict[str, str]) -> Typeset:
    """Compiles <paper_dir>/paper.typ with `inputs` as sys.inputs."""
    compiler = paper_compiler(paper_dir, inputs)

    def query(selector: str) -> list[dict]:
        return json.loads(compiler.query(selector, format="json"))

    def label(node: dict) -> str:
        return node["label"].strip("<>")

    try:
        pdf, warnings = compiler.compile_with_warnings(format="pdf")
        pngs = compiler.compile(format="png", ppi=PPI)
        if not isinstance(pdf, bytes) or pngs is None:
            raise BuildError("Typst returned no PDF, or no page images")
        abstract = query("<abstract>")
        references = query("<references>")
        figures = query("figure")
        typeset = Typeset(
            pdf=pdf,
            pngs=pngs if isinstance(pngs, list) else [pngs],
            warnings=[warning.message for warning in warnings],
            abstract=" ".join(plain(abstract[0]["value"]).split()) if abstract else "",
            missing=[f"{m['value']['key']}: {m['value']['why']}" for m in query("<missing>")],
            claims=[(c["value"]["ok"], c["value"]["text"]) for c in query("<claim>")],
            todos=len(query("<todo>")),
            references=(references[0]["value"]["page"], references[0]["value"]["y"]) if references else None,
            figures=[label(f) if "label" in f else plain(f["caption"]["body"]) for f in figures],
            refs={ref["target"].strip("<>") for ref in query("ref")},
            cites={cite["key"].strip("<>") for cite in query("cite")},
            headings=[plain(heading["body"]) for heading in query("heading")],
            links=[link["dest"] for link in query("link") if isinstance(link["dest"], str)],
            misplaced=[
                (
                    m["value"]["label"] or plain(m["value"]["caption"]),
                    plain(m["value"]["written"]),
                    plain(m["value"]["drawn"]),
                )
                for m in query("<misplaced>")
            ],
        )
    except typst.TypstError as error:
        raise BuildError(error.diagnostic or error.message) from None
    return typeset
