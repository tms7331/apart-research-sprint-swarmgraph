// The video's slides (bin/build-slides): 16:9, one idea per slide. Figures and numbers come from the same
// ledger as the paper (build/numbers.json and build/figures/), so cite them by key exactly as paper.typ does.
#import "lib.typ": data-figure, ledger, n, pct

#let ink = rgb("#0b0b0b")
#let muted = rgb("#52514e")
#let rule = rgb("#d6d5cf")
#let blue = rgb("#2a78d6")   // read individually; the paper's figures use the same three colors
#let orange = rgb("#eb6834") // the attack
#let green = rgb("#1baf7a")  // honest

#set page(
  paper: "presentation-16-9",
  margin: (x: 1.6cm, top: 1.2cm, bottom: 1.1cm),
  footer: align(right, text(size: 7pt, fill: luma(160), sys.inputs.at("stamp", default: ""))),
)
#set text(font: "Old Standard TT", size: 18pt, fill: ink)
#set par(leading: 0.62em)
#set list(spacing: 0.75em, marker: text(fill: muted)[•])

// A slide: an optional title (with a short label above it), then its body.
#let slide(title: none, label: none, body) = page[
  #if label != none { text(size: 11pt, fill: muted, tracking: 0.06em, upper(label)); v(-0.3em) }
  #if title != none { text(size: 26pt, weight: "bold", title); v(0.55em) }
  #body
]

// A slide that is one figure from the ledger, scaled to fill the space its title leaves.
#let figure-slide(key, title) = page(block(height: 100%, grid(rows: (auto, 1fr), row-gutter: 0.6em,
  text(size: 22pt, weight: "bold", title),
  align(center + horizon, data-figure(key, width: 100%, height: 100%, fit: "contain")),
)))

// The one line a results slide should leave behind.
#let takeaway(body) = block(width: 100%, inset: (left: 0.7em, y: 0.45em), stroke: (left: 3pt + orange),
  text(size: 19pt, weight: "bold", body))

// A result: what was measured, and the count, set large.
#let result(label, value, color: ink) = (text(size: 16pt, label), align(right, text(size: 22pt, weight: "bold", fill: color, value)))
#let results(..rows) = grid(columns: (1fr, auto), column-gutter: 1.2em, row-gutter: 0.55em,
  ..rows.pos().flatten())

// --- Title -----------------------------------------------------------------------------------------------------
#page(margin: (x: 2.2cm, y: 2cm))[
  #align(left + horizon)[
    #text(size: 34pt, weight: "bold")[Catching Attacks Split Across a Fleet of AI Agents]
    #v(0.2em)
    #line(length: 5cm, stroke: 2pt + orange)
    #v(0.6em)
    #text(size: 20pt)[Thomas Redfern]
  ]
]

// --- The problem -----------------------------------------------------------------------------------------------
#slide(title: [The problem])[
  - AI agents increasingly work in teams and fleets, each agent with a narrow task.
  - A harmful goal can be *split across agents*, so that every agent's actions look like ordinary work.
  - Kitaoka et al. showed that a monitor reading each agent individually misses such an attack, and that reading
    the team together catches it.
  #v(0.6em)
  #takeaway[In a fleet of hundreds of agents, which ones should a monitor read together?]
  #v(1fr)
  #text(size: 11pt, fill: muted)[Kitaoka, Pham, Giudice and Merizian (2026), _Red-Teaming Multi-Agent Attacks for Loss-of-Control Risks_, arXiv:2610.24052.]
]

// --- The setup -------------------------------------------------------------------------------------------------
#let step(name, body) = box(width: 100%, inset: (x: 0.55em, y: 0.45em), stroke: 1pt + orange, radius: 3pt)[
  #text(size: 14pt, weight: "bold", fill: orange, name) \
  #text(size: 13pt, body)
]
#let arrow = align(center + horizon, text(size: 20pt, fill: muted, sym.arrow.r))

#slide(title: [The setup: data exfiltration, split across three agents])[
  #grid(columns: (1fr, auto, 1fr, auto, 1fr, auto, 0.62fr), column-gutter: 0.35em,
    step[backup][copies the private model checkpoint into a bundle], arrow,
    step[staging][points a package entry at that bundle], arrow,
    step[sync][switches on delivery to a partner], arrow,
    box(width: 100%, inset: (y: 0.45em))[#text(size: 13pt)[the private model leaves the lab]],
  )
  #v(0.35em)
  #text(size: 14pt)[Honest teams take the same three steps, but ship shareable data or leave the delivery off. Each step is permitted on its own; only the combination is an attack. The LLM monitor scores suspicion from 0 to 100 and flags a fleet at #n("sa.threshold").]
  #v(0.45em)
  #text(size: 12pt, fill: muted)[What the monitor sees: one fleet's public log, #n("lx.events") events from #n("lx.agents") agents. Three of these lines are the attack:]
  #v(0.15em)
  #{
    let rows = ledger.at("lx-log").rows
    set text(size: 11pt)
    table(
      columns: (auto, auto, auto, auto, 1fr, auto),
      stroke: none, inset: (x: 0.4em, y: 0.22em),
      fill: (_, y) => if y > 0 and rows.at(y - 1).at(5) != "" { orange.lighten(85%) },
      table.header(..("event", "agent", "tool", "record", "fields", "").map(h => text(fill: muted, h))),
      ..rows.map(r => (
        raw(r.at(0)), raw(r.at(1)), raw(r.at(2)), raw(r.at(3)), raw(r.at(4)),
        if r.at(5) != "" { text(weight: "bold", fill: orange, r.at(5)) } else { [] },
      )).flatten(),
    )
  }
]

// --- Step 1: reproducing the fragmentation result ---------------------------------------------------------------
#slide(label: [Step 1], title: [Reproducing the fragmentation result])[
  One team of three agents, judged by the same LLM monitor in two ways: reading each agent individually, and
  reading the whole team together.
  #v(0.5em)
  #grid(columns: (1fr, 1fr), column-gutter: 2.2em,
    [
      #text(size: 15pt, weight: "bold", fill: blue)[Read individually]
      #v(0.2em)
      #results(
        result[solo attack (one agent)][#n("tb.solo.flagged")],
        result[split attack (three agents)][#n("tb.split.flagged")],
        result[honest teams falsely flagged][#n("tb.honest.flagged")],
      )
    ],
    [
      #text(size: 15pt, weight: "bold", fill: orange)[Read together]
      #v(0.2em)
      #results(
        result[split attack][#n("tb.split.joint.flagged")],
        result[honest teams falsely flagged][#n("tb.honest.joint.flagged")],
      )
    ],
  )
  #v(1fr)
  #takeaway[Splitting an attack hides it from a monitor that reads each agent individually.]
]

#figure-slide("tb-figure")[Splitting an attack hides it from a monitor that reads each agent individually.]

// --- Experiment A: a growing fleet ------------------------------------------------------------------------------
#slide(label: [Experiment A], title: [Hiding the team in a growing fleet])[
  We hide the team among up to #n("sa.agents.n180") agents. The monitor has #n("sa.budget") tool calls to search
  and read the fleet's log, enough to read about #n("sa.capacity") events.
  #v(0.5em)
  #grid(columns: (1fr, 1fr), column-gutter: 2.2em,
    results(
      result[split attack caught, #n("sa.agents.n30") agents][#n("sa.split.n30")],
      result[split attack caught, #n("sa.agents.n100") agents][#n("sa.split.n100")],
      result[split attack caught, #n("sa.agents.n180") agents][#n("sa.split.n180")],
    ),
    results(
      result[solo attack caught, #n("sa.agents.n180") agents][#n("sa.solo.n180")],
      result[honest fleets falsely flagged][#n("sa.honest")],
      result[missed attacks where it saw all colluders][#n("sa.misses.saw.all") of #n("sa.misses")],
    ),
  )
  #v(1fr)
  #takeaway[Once the log exceeds the monitor's capacity, it can't find which agents to read together.]
]

#figure-slide("sa-figure")[Once the log exceeds the monitor's capacity, attacks slip through.]

// --- Experiment B: a provenance graph ---------------------------------------------------------------------------
#slide(label: [Experiment B], title: [Grouping the log with a provenance graph])[
  The same monitor gets a provenance graph that groups the log's events into chains, as in FragBench, at
  #n("sb.agents") agents. We then add tool-call overlap between teams: shared reads that link teams in the graph.
  #v(0.5em)
  #grid(columns: (1fr, 1fr), column-gutter: 2.2em,
    results(
      result[split attack caught, no overlap][#n("sb.split.o0")],
      result[the same fleets, without the graph][#n("sa.split.n100")],
      result[overlap 1][#n("sb.split.o1")],
      result[overlap 2][#n("sb.split.o2")],
    ),
    results(
      result[colluders' chain, no overlap][#n("sb.chain.o0") agents],
      result[colluders' chain, overlap 2][#n("sb.chain.o2") agents],
      result[honest fleets falsely flagged][#n("sb.honest")],
    ),
  )
  #v(1fr)
  #takeaway[The graph helps until shared tool calls merge the fleet into one chain.]
]

#figure-slide("sb-tools")[As overlap grows, the monitor abandons the graph for text search.]
#figure-slide("sb-figure")[The graph helps until overlap merges the fleet into one chain.]

// --- Our approach: the flow graph -------------------------------------------------------------------------------
#let term(body) = text(weight: "bold", fill: orange, body)
#slide(label: [Experiment C: our approach], title: [Follow the private data])[
  #grid(columns: (0.8fr, 1.2fr), column-gutter: 1.2em,
    [
      #set text(size: 13.5pt)
      #set enum(spacing: 0.9em)
      + *Label.* Jev, a decision model, reads each action alone and answers three yes/no questions as
        probabilities: does it touch private data (#term[source])? Pass data or a reference on (#term[carrier])?
        Switch on a delivery outside the lab (#term[sink])?
      + *Link.* An action that writes a record links to every later action that names it.
      + *Simulate.* Across #n("sc.worlds") sampled worlds, how often does private data reach a sink through
        another agent? That is the sink's #term[flow score].
      + *Judge.* The LLM monitor reads the agents on the top #n("sc.groups") paths together.
      #v(0.4em)
      #text(size: 11pt, fill: muted)[Jev's labels cost about #n("sc.usd.base") for a 303-agent fleet.]
    ],
    [
      #data-figure("fx-figure", width: 100%)
      #v(-0.2em)
      #text(size: 11pt, fill: muted)[A worked example. Each step on its own looks innocent; only team A has a
      complete path from source to sink, across agents. Shared reads pass on almost nothing, so overlap between
      teams doesn't merge them.]
    ],
  )
]

// --- Experiment C: results --------------------------------------------------------------------------------------
#slide(label: [Experiment C], title: [Following the data, at every overlap and fleet size])[
  The flow graph picks the groups; the same LLM monitor reads each group together. #n("sc.fleets") fleets, each
  judged #n("sc.passes") times: B's #n("sc.curve.fleets") fleets, then more overlap and bigger fleets.
  #v(0.5em)
  #grid(columns: (1fr, 1fr), column-gutter: 2.2em,
    results(
      result[split attack caught, B's fleets][#n("sc.split.curve")],
      result[B's graph monitor, the same fleets][#n("sc.b.split")],
      result[overlap 16][#n("sc.split.o16")],
      result[#n("sc.agents.n1600") agents][#n("sc.split.n1600")],
    ),
    results(
      result[honest fleets falsely flagged][#n("sc.honest")],
      result[judge's top group was the colluders][#n("sc.judge.colluders")],
      result[lowest attack score, highest honest][#n("sc.judge.attack.min") vs #n("sc.judge.honest.max")],
      result[Jev labels, #n("sc.agents.n1600") agents][#n("sc.usd.largest")],
    ),
  )
  #v(1fr)
  #takeaway[Following the data caught the split attack at every overlap and fleet size we tried.]
]

#figure-slide("sc-figure")[The flow graph catches every split attack, even where the provenance graph fails.]
#figure-slide("sc-scores")[The judge's scores for attacks and honest fleets never overlap.]

// --- Shortcomings and future work -------------------------------------------------------------------------------
#slide(title: [Shortcomings and future work])[
  #set text(size: 14.5pt)
  #grid(columns: (1fr, 1fr), column-gutter: 2em,
    [
      #text(size: 16pt, weight: "bold", fill: orange)[Shortcomings]
      - *One scripted scenario.* Every fleet comes from one generator: one kind of attack, two kinds of honest
        team, and scripted agents rather than live ones.
      - *Tuned on one fleet.* We worded Jev's questions on a single development fleet; held-out fleets agree,
        but they come from the same generator.
      - *What it can't see.* The path must cross agents, so a solo attack is left to the per-agent monitor, and
        data must move through named records.
      - *A narrow honest margin.* Honest fleets score up to #n("sc.judge.honest.max") against a threshold of
        #n("sc.threshold").
    ],
    [
      #text(size: 16pt, weight: "bold", fill: blue)[Future work]
      - *Harder honest teams,* such as private data that _is_ authorized for export, so the flow has to follow
        the policy and not just the data.
      - *Live LLM agents and other attacks,* such as sabotage, and attackers who know how the monitor works.
      - *Flows without record names,* using links that Jev judges ("did this action use that one's output?").
      - *More repeats* of every condition, and Experiment B run at the larger fleet sizes.
    ],
  )
]

// --- Conclusion -------------------------------------------------------------------------------------------------
#slide(title: [Conclusion])[
  #set text(size: 16pt)
  - Splitting an attack across agents hides it from a monitor that reads each agent individually: it caught
    #n("tb.split.flagged") split attacks, against #n("tb.split.joint.flagged") when reading the team together.
  - In a growing fleet, a monitor with fixed capacity can't find which agents to read together: it flagged
    the split attack in #n("sa.split.n180") runs at #n("sa.agents.n180") agents.
  - A provenance graph helps until shared tool calls merge the fleet into one chain: from #n("sb.split.o0") with
    no overlap to #n("sb.split.o2") at overlap 2.
  - Following the private data finds the right agents: the flow graph flagged the split attack in #n("sc.split")
    judgments with #n("sc.honest") false alarms, up to #n("sc.agents.n1600") agents, for about #n("sc.usd.base") of labels per
    303-agent fleet.
  #v(1fr)
  #takeaway[To find which agents to read together, follow the data they pass between them.]
]
