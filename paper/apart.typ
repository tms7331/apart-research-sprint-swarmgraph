// Clone of the official Apart Research sprint template (the Google Doc that requirements.md links).
// Preexisting: written before this sprint in Jason's earlier run (apart-oneshot-collusion 36de5f2,
// 2026-10-22), refined in github.com/carver/apart-research-collusion-sprint-2026 (5134da7,
// 2026-10-26), our AI Collusion Research Sprint project, and copied here for the
// Swarm Alignment Hackathon; git log shows each change since. The paper imports it through lib.typ.
// Layout facts taken from the docx: US Letter, 1-inch margins, Old Standard TT throughout,
// body 11 pt at 1.15 line spacing, title 20 pt bold between a 3 pt and a 1 pt rule,
// section headings 14 pt bold and subsection headings 13 pt bold, both black (since the
// template's restyle by 2026-10-23), abstract heading 14 pt bold centred, abstract body italic,
// justified and inset (~0.99 in left, ~1.13 in right), "-" bullets (we use "•"), footnotes 10 pt.
// Fonts: bin/build-paper passes paper/fonts/.

#let link-blue = rgb("#1155cc")

// The marks on every page of a draft: a faint diagonal watermark, and a footer with the stamp
// (the commit and build time).
#let draft-marks(stamp) = (
  background: rotate(-45deg, text(fill: luma(88%), weight: "bold", align(center)[
    #text(size: 96pt)[DRAFT] \ #text(size: 24pt)[not for submission]
  ])),
  footer: align(center, text(size: 8pt, fill: luma(40%))[DRAFT, not for submission · #stamp]),
)

#let apart(
  title: "Project Title",
  authors: (),
  abstract: [],
  sprint-name: "Swarm Alignment Hackathon",
  sprint-url: "https://apartresearch.com/sprints/swarm-alignment-2026",
  sprint-date: "November 2026",
  draft: true,
  stamp: "",
  commit: "",
  body,
) = {
  set document(title: title, description: if commit != "" { "Built from commit " + commit })
  // The template PDF carries no page numbers; set numbering: "1" here to add them.
  set page(paper: "us-letter", margin: 1in, ..if draft { draft-marks(stamp) })
  set text(font: "Old Standard TT", size: 11pt, lang: "en", top-edge: "ascender", bottom-edge: "descender")
  // Google Docs "1.15" on Old Standard TT gives ~15.5 pt from baseline to baseline at 11 pt.
  set par(leading: 0.41em, spacing: 0.8em, justify: false)
  // A URL's link; one to a place in the paper (a reference) prints like the text around it.
  show link: it => if type(it.dest) == str { text(fill: link-blue, underline(it)) } else { it }

  set footnote.entry(separator: line(length: 2in, stroke: 0.5pt), gap: 0.4em)
  show footnote.entry: set text(size: 10pt)

  // Section headings: "1. Introduction", 14 pt bold (docx Heading2 as used).
  set heading(numbering: (..n) => if n.pos().len() == 1 { numbering("1.", ..n) })
  show heading.where(level: 1): it => {
    set text(size: 14pt, weight: "bold")
    set par(justify: false)
    block(above: 1.35em, below: 0.75em, sticky: true, {
      if it.numbering != none and it.outlined { counter(heading).display(it.numbering) + h(0.3em) }
      it.body
    })
  }
  // Subsections ("Limitations", "Future Work"): 13 pt bold, unnumbered.
  show heading.where(level: 2): it => {
    set text(size: 13pt, weight: "bold")
    block(above: 1.1em, below: 0.6em, sticky: true, it.body)
  }
  show heading.where(level: 3): it => {
    set text(size: 11pt, weight: "bold")
    block(above: 0.9em, below: 0.5em, sticky: true, it.body)
  }

  set figure(gap: 0.6em)
  show figure.caption: set text(size: 10pt)
  show figure.caption: set par(justify: true)
  show figure.caption: set align(left)
  show figure.where(kind: table): set figure.caption(position: top)
  set table(stroke: 0.5pt + luma(140), inset: (x: 4pt, y: 2.5pt))
  show table: set text(size: 9pt)
  show table: set par(justify: false, leading: 0.3em)

  set list(indent: 0.6em, body-indent: 0.6em, marker: [•])
  set enum(indent: 0.6em)

  // ---- Title block ------------------------------------------------------------------
  v(0.25in)
  line(length: 100%, stroke: 3pt)
  v(14pt)
  align(center, text(size: 20pt, weight: "bold", hyphenate: false, {
    set par(leading: 0.2em)
    title
    footnote(numbering: "1")[#h(0.2em)Research conducted at the #link(sprint-url)[#sprint-name], #sprint-date]
  }))
  v(15pt)
  line(length: 100%, stroke: 1pt)
  v(21pt)

  // Author block: a centred grid of up to three authors per row (docx Table2, 5 in wide).
  // The author block and "With Apart Research" use single line spacing, as in the docx.
  let cols = calc.min(calc.max(authors.len(), 1), 3)
  {
    set par(leading: 0.22em)
    align(center, block(width: if cols == 1 { 2.6in } else { 5in }, grid(
      columns: (1fr,) * cols,
      row-gutter: 11pt,
      ..authors.map(a => align(center, [#a.name \ #a.affiliation])),
    )))
    v(6pt)
    align(center)[*With* \ Apart Research]
  }

  // Abstract. The metadata lets bin/build-paper count its words.
  [#metadata(abstract) <abstract>]
  v(12pt)
  align(center, text(size: 14pt, weight: "bold")[Abstract])
  v(16pt)
  pad(left: 0.99in, right: 1.13in, par(justify: true, emph(abstract)))
  v(10pt)

  body
}

// Unnumbered section heading in the level-1 style (Code and Data, References, Appendix).
#let unnumbered(title) = heading(level: 1, numbering: none, outlined: false, title)

// Appendix sections lettered A, B, ...
#let appendix(body) = {
  counter(heading).update(0)
  set heading(numbering: (..n) => if n.pos().len() == 1 { numbering("A.", ..n) })
  body
}
