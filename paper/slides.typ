// The video's slides (bin/build-slides): 16:9, one idea per slide. Figures and numbers come from the same
// ledger as the paper (build/numbers.json and build/figures/), so cite them by key exactly as paper.typ does.
#import "lib.typ": data-figure, n, pct

#set page(
  paper: "presentation-16-9",
  margin: (x: 1.4cm, top: 1.1cm, bottom: 1.0cm),
  footer: align(right, text(size: 7pt, fill: luma(150), sys.inputs.at("stamp", default: ""))),
)
#set text(font: "Old Standard TT", size: 20pt)

// A slide: an optional title, then its body.
#let slide(title: none, body) = page[
  #if title != none {
    text(size: 22pt, weight: "bold", title)
    v(0.5em)
  }
  #body
]

// A slide that is one figure from the ledger, scaled to fit the space under its title.
#let figure-slide(key, title) = slide(title: title)[
  #align(center + horizon, data-figure(key, width: 100%, height: 11.2cm, fit: "contain"))
]

#figure-slide("tb-figure")[Splitting an attack hides it from a monitor that reads each agent individually.]
#figure-slide("sa-figure")[Once the log exceeds the monitor's capacity, attacks slip through.]
#figure-slide("sb-tools")[As overlap grows, the monitor abandons the graph for text search.]
#figure-slide("sb-figure")[The graph helps until overlap merges the fleet into one chain.]
#figure-slide("sc-figure")[The flow graph catches every split attack, even where the provenance graph fails.]
#figure-slide("sc-scores")[The judge's scores for attacks and honest fleets never overlap.]
