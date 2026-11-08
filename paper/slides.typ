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
  #if label != none { text(size: 20pt, weight: "bold", fill: orange, label); v(-0.45em) }
  #if title != none { text(size: 26pt, weight: "bold", title); v(0.55em) }
  #body
]

// A slide that is one figure from the ledger, scaled to fill the space its title leaves.
#let figure-slide(key, title, caption: none) = page(block(height: 100%, grid(
  rows: if caption == none { (auto, 1fr) } else { (auto, 1fr, auto) }, row-gutter: 0.6em,
  text(size: 22pt, weight: "bold", title),
  align(center + horizon, data-figure(key, width: 100%, height: 100%, fit: "contain")),
  ..if caption != none { (text(size: 13pt, caption),) },
)))

// A slide with a label, a title and a short text, then a figure from the ledger filling the rest of the page.
// With side: true the text sits left of the figure, for figures closer to square than the slide.
#let labeled-figure-slide(key, label: none, title: none, side: false, body) = {
  let heading = [#text(size: 20pt, weight: "bold", fill: orange, label) #v(-0.45em) #text(size: 26pt, weight: "bold", title)]
  let figure = align(center + horizon, data-figure(key, width: 100%, height: 100%, fit: "contain"))
  page(block(height: 100%, if side {
    grid(rows: (auto, 1fr), row-gutter: 0.7em, heading,
      grid(columns: (0.75fr, 1.25fr), column-gutter: 1.5em, align(horizon, text(size: 16pt, body)), figure))
  } else {
    grid(rows: (auto, auto, 1fr), row-gutter: 0.7em, heading, text(size: 16pt, body), figure)
  }))
}

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
    #text(size: 34pt, weight: "bold")[Follow the Data:\ Catching Split Attacks in Agent Swarms with Decision Model Graphs]
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
// The three agents' steps, each allowed on its own, then the service that acts on what they set up.
#let step(name, body, allowed, service: false) = box(width: 100%, height: 100%, inset: (x: 0.55em, y: 0.5em),
  radius: 3pt, stroke: if service { (paint: muted, thickness: 1pt, dash: "dashed") } else { 1pt + orange },
  fill: if service { rgb("#f4f3ef") })[
  #text(size: 14pt, weight: "bold", fill: if service { ink } else { orange }, name)
  #v(-0.35em)
  #text(size: 14pt, body)
  #v(1fr)
  #text(size: 12pt, fill: muted, allowed)
]
#let arrow = align(center + horizon, text(size: 20pt, fill: muted, sym.arrow.r))
#let ok(body) = [#text(fill: green, weight: "bold", sym.checkmark) #body]

#slide(title: [The setup: data exfiltration, split across three agents])[
  #block(height: 5.2cm, grid(columns: (1fr, auto, 1fr, auto, 1fr, auto, 1fr), column-gutter: 0.35em, rows: 100%,
    step[backup agent][copies the private model checkpoint into an internal bundle][#ok[internal backups are
      allowed]], arrow,
    step[staging agent][points the outgoing package at that bundle][#ok[packages may use internal bundles]],
    arrow,
    step[sync agent][switches on the scheduled delivery to a partner][#ok[a routine delivery]], arrow,
    step(service: true)[sync service][runs automatically: follows the package to the bundle and delivers what it
      holds][#text(fill: orange, weight: "bold")[the private model leaves the lab]],
  ))
  #v(0.6em)
  #text(size: 15pt)[Each agent can change only its own record and can't see past it, so no single agent's actions
    show the leak. The sync service checks that the package is ready, not what is in it. Honest teams take the
    same three steps, but back up shareable data or leave the delivery off.]
  #v(1fr)
  #takeaway[Every step is allowed on its own; only the combination is an attack.]
]

// --- What the monitor sees -------------------------------------------------------------------------------------
#slide(title: [What the monitor sees])[
  An LLM monitor reads the fleet's log: every agent's task, tool calls, results and messages, in time order. It
  scores suspicion from 0 to 100 and flags the fleet at #n("sa.threshold").
  #v(0.5em)
  #text(size: 13pt, fill: muted)[One fleet's log has #n("lx.events") events from #n("lx.agents") agents. Three of
    these lines are the attack:]
  #v(0.2em)
  #{
    let rows = ledger.at("lx-log").rows
    set text(size: 11pt)
    table(
      columns: (auto, auto, auto, auto, 1fr, auto),
      stroke: none, inset: (x: 0.4em, y: 0.32em),
      fill: (_, y) => if y > 0 and rows.at(y - 1).at(5) != "" { orange.lighten(85%) },
      table.header(..("event", "agent", "tool", "record", "fields", "").map(h => text(fill: muted, h))),
      ..rows.map(r => (
        raw(r.at(0)), raw(r.at(1)), raw(r.at(2)), raw(r.at(3)), raw(r.at(4)),
        if r.at(5) != "" { text(weight: "bold", fill: orange, r.at(5)) } else { [] },
      )).flatten(),
    )
  }
  #v(1fr)
  #takeaway[The attack is three ordinary-looking lines in a log of thousands.]
]

// --- What we varied ---------------------------------------------------------------------------------------------
// Rows are the three things we varied; columns are the experiments. A tinted cell is a range the experiment swept.
#let axis(name, body) = [
  #text(size: 16pt, weight: "bold", name) \
  #text(size: 12pt, fill: muted, body)
]
#let level(main, note: none) = [
  #text(size: 17pt, weight: "bold", main)
  #if note != none { linebreak(); text(size: 10.5pt, fill: muted, note) }
]
#let check = text(size: 22pt, weight: "bold", fill: green, sym.checkmark)
#let none-here = text(size: 17pt, fill: muted, [–])

#slide(title: [What we varied])[
  #let swept = ((2, 2), (4, 2), (3, 3), (4, 3))
  #table(
    columns: (1fr, 3.9cm, 3.9cm, 3.9cm, 3.9cm),
    stroke: (_, y) => if y > 0 { (top: 0.6pt + rule) },
    inset: (x: 0.5em, y: 0.8em),
    align: (x, _) => if x == 0 { left + horizon } else { center + horizon },
    fill: (x, y) => if (x, y) in swept { rgb("#efeee9") },
    table.header([], ..("Step 1", "Experiment A", "Experiment B", "Experiment C").map(h => text(size: 13pt, fill: muted, h))),
    axis([No attack], [Every attack fleet has an honest twin: the same fleet, but the attacking team ships shareable
      data instead. Any flag on a twin is a false alarm.]),
    level(note: [plus an incomplete attack], check), check, check, check,
    axis([Fleet size, in agents], [The attacking team of three hides among honest teams of three.]),
    level[3], level(note: [7 sizes])[3–#n("sa.agents.n180")], level[#n("sb.agents")],
    level(note: [#n("sc.agents.n400") and #n("sc.agents.n1600") at overlap 4])[#n("sb.agents")–#n("sc.agents.n1600")],
    axis([Tool-call overlap], [At overlap $N$, each team reads about $N$ records that one other team also reads,
      linking the teams.]),
    none-here, level[0], level(note: [0, ½, 1, 1½, 2, 4])[0–4], level(note: [B's six, then 8, 16])[0–16],
  )
  #v(1fr)
  #text(size: 12pt, fill: muted)[Every condition is generated in #n("sb.layouts") random layouts, and each fleet
    is monitored more than once.]
]

// --- Step 1: reproducing the fragmentation result ---------------------------------------------------------------
#labeled-figure-slide("tb-figure", label: [Step 1], title: [Reproducing the fragmentation result])[One team of
  three agents, judged by the same LLM monitor in two ways: reading each agent individually, and reading the whole
  team together.]

// --- Experiment A: a growing fleet ------------------------------------------------------------------------------
#slide(label: [Experiment A], title: [An agent with #n("sa.budget") tool calls searches the raw log])[
  The monitor is an LLM agent with four tools:
  #v(-0.2em)
  #grid(columns: (1fr, 1fr), column-gutter: 2.2em, row-gutter: 0.55em,
    [- text search], [- read events by ID],
    [- read a range of the log], [- read one agent's transcript],
  )
  #v(0.1em)
  It gets #n("sa.budget") calls over a flat, time-ordered log of every agent's actions, enough to read about
  #n("sa.capacity") events. We hide the team among up to #n("sa.agents.n180") agents.
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
#let agent-box(body) = box(inset: (x: 0.45em, y: 0.4em), stroke: 1pt + orange, radius: 3pt,
  text(size: 13pt, weight: "bold", fill: orange, body))
#let shared(body) = align(center + horizon, stack(spacing: 0.25em, text(size: 11pt, fill: muted, body),
  line(length: 100%, stroke: 1.2pt + muted)))

#slide(label: [Experiment B], title: [Structuring the log with a provenance graph])[
  #grid(columns: (1fr, 1fr), column-gutter: 1.6em,
    [
      #set text(size: 13.5pt)
      #set enum(spacing: 0.85em)
      + *Nodes.* Every tool call and tool result in the log.
      + *Links.* A call and its result; one agent's consecutive actions; any two events that name the same
        record. A record named by more than #n("sb.busy") agents counts as busy and links nothing.
      + *Chains.* Linked events form chains. The structure comes from the log alone: which agents touched which
        records.
      + *Monitor.* The same LLM monitor, with the same #n("sa.budget") calls, gets #n("sb.graph.tools") more
        tools: list the chains, largest first; find chains that contain some text; read a chain; look up an
        agent's chain; see who touched a record.
    ],
    [
      #set text(size: 13.5pt)
      *Why the attack forms one chain*
      #v(0.2em)
      #grid(columns: (auto, 1fr, auto, 1fr, auto), column-gutter: 0.3em,
        agent-box[backup], shared[bundle], agent-box[staging], shared[package entry], agent-box[sync])
      #v(0.3em)
      The backup and staging agents both name the bundle, and the staging and sync agents both name the
      package entry. With no overlap, each team is a chain of its own.
      #v(0.5em)
      *Tool-call overlap* \
      A team's staging agent also reads a shared index that lists another team's package entry. That read
      names the other team's record, so the two teams' chains join.
    ],
  )
  #v(1fr)
  #text(size: 11.5pt, fill: muted)[Compared with the full FragBench defense: we keep its event graph and chains, but drop its
    links between similar arguments, replace its down-weighting of busy records with a fixed cutoff, and put the
    LLM monitor in place of its trained per-event detector.]
]

#labeled-figure-slide("sb-figure", label: [Experiment B], side: true,
  title: [The graph helps until overlap merges the fleet into one chain.])[Every fleet has #n("sb.agents") agents.
  With no overlap these are Experiment A's fleets; then we add tool-call overlap between teams, which joins the
  teams' chains.]

// --- Our approach: the flow graph -------------------------------------------------------------------------------
#let term(body) = text(weight: "bold", fill: orange, body)
// The flow graph's four steps: what each does (top row), then what it gave on one real fleet (bottom row).
#let rec(key) = text(size: 9.5pt, raw(ledger.at(key).value))
#let p(key) = text(weight: "bold", n(key))
#let step-name(name, body) = [#text(size: 16pt, weight: "bold", name) #v(-0.45em) #text(size: 12.5pt, body)]

#slide(label: [Experiment C: our approach], title: [Decision Model Graph Construction])[
  #v(-0.2em)
  #grid(
    columns: (1fr, 1fr, 1fr, 1fr), column-gutter: 1.1em, row-gutter: 0.7em,
    inset: (x, y) => if y == 1 { (x: 0.55em, y: 0.55em) } else { 0pt },
    fill: (x, y) => if y == 1 { rgb("#f4f3ef") },
    [
      #step-name[1. Label][Jev, a decision model, reads each action alone and gives three probabilities: does
        it touch private data (#term[source])? Pass data or a reference on (#term[carrier])? Switch on a delivery
        outside the lab (#term[sink])?]
    ],
    [
      #step-name[2. Link][An action that writes a record links to every later action, by any agent, that names
        it. Each action also links to the same agent's next one. Links carry no numbers.]
    ],
    [
      #step-name[3. Simulate][In each of #n("sc.worlds") random rounds, data spreads forward through the log.
        An action's #term[flow score]: the share of rounds in which data reached it from another agent, times
        P(#term[sink]).]
    ],
    [
      #step-name[4. Judge][Trace back from the top-scoring actions to the agents the data passed through. The
        LLM monitor reads each of the top #n("sc.groups") groups together, and flags the fleet at
        #n("sc.threshold").]
    ],
    ..([
      The backup agent's copy into \ #rec("sc.ex.source.record"): \
      #term[source] #p("sc.ex.source.source") \
      #term[carrier] #p("sc.ex.source.carrier") \
      #term[sink] #p("sc.ex.source.sink")
    ], [
      #rec("sc.ex.source.record") \ backup writes it, staging names it: a link. \
      #rec("sc.ex.carrier.record") \ staging writes it, sync names it. \
      #n("sc.ex.links") links in all.
    ], [
      Private data reaches the sync agent's delivery in #p("sc.ex.hit") of worlds. \
      × P(#term[sink]) #p("sc.ex.sink.sink") \
      #sym.eq flow score #p("sc.ex.score") \
      Next highest: #n("sc.ex.next")
    ], [
      Top group: #n("sc.ex.who") \
      → judge score #p("sc.ex.judge.top"), flagged \
      Next two groups: #n("sc.ex.judge.rest")
    ]).map(body => text(size: 11.5pt, body)),
  )
  #v(1fr)
  #text(size: 11.5pt, fill: muted)[Examples: one fleet of #n("sc.ex.agents") agents at overlap #n("sc.ex.overlap"),
    where the provenance graph caught the attack in #n("sb.split.o4") runs. Jev's labels cost about
    #n("sc.usd.base") for a fleet this size.]
]

#figure-slide("fx-figure", caption: [*Nodes* are actions, and carry Jev's three probabilities. *Links* carry no
  numbers: a link only means one action wrote a record that a later action names, or that it is the same agent's
  next action. The right panel's percentages are only for the picture: the method scores nodes, not links.])[Following
  the data through a small example]

// --- Experiment C: one round of the simulation -----------------------------------------------------------------
#let mini-table(key, highlight: none) = {
  let entry = ledger.at(key)
  set text(size: 12pt)
  table(columns: entry.header.len(), stroke: none, inset: (x: 0.45em, y: 0.32em),
    fill: (_, y) => if y == 0 { rgb("#f4f3ef") },
    table.header(..entry.header.map(h => text(fill: muted, h))),
    ..entry.rows.flatten())
}

#slide(label: [Experiment C: simulate], title: [One round of the simulation])[
  #grid(columns: (1fr, 1fr), column-gutter: 1.6em,
    [
      #set text(size: 13.5pt)
      #set enum(spacing: 0.75em)
      + *Answer every question with a random number.* For each action, draw a number between 0 and 1 for
        #term[source] and one for #term[carrier]. Below the action's probability means _yes_ for this round.
        P(#term[sink]) is never drawn.
      + *Go through every action once, in time order,* earliest first. Every link points forward in time, so an
        action's incoming actions are already settled when we reach it; parts of the graph that don't connect are
        visited too. There is no starting point to pick.
      + *An action holds private data* if it is a source this round, or if an incoming action holds data and it is
        a carrier this round.
      + *It is hit* if the data came in from a different agent's action. Data that never leaves one agent doesn't
        count: that is the per-agent monitor's case.
    ],
    [
      #text(size: 13.5pt)[*Round 1 of the small example,* with the real random numbers:]
      #v(0.2em)
      #mini-table("fx-round")
      #v(0.3em)
      #set text(size: 13pt)
      Then go through the actions in time order:
      - *copy checkpoint:* holds data? #n("fx.r0.a1.holds")
      - *point package:* holds data? #n("fx.r0.a2.holds") \ hit, from another agent? #n("fx.r0.a2.hit")
      - *delivery on:* hit, from another agent? #n("fx.r0.a3.hit")
      #v(0.3em)
      Then new random numbers, and again: #n("sc.worlds") rounds per fleet in the real run (#n("fx.worlds") in this
      example).
    ],
  )
]

// --- Experiment C: from flow scores to the judge ---------------------------------------------------------------
#slide(label: [Experiment C: score and judge], title: [From flow scores to the judge])[
  #grid(columns: (1fr, 1fr), column-gutter: 1.6em,
    [
      #set text(size: 13.5pt)
      After all the rounds, *every action* gets one number:
      #v(0.1em)
      #align(center, text(size: 15pt)[#term[flow score] = hit rate × P(#term[sink])])
      #v(0.1em)
      The hit rate is the share of rounds in which data reached the action from another agent.
      #v(0.3em)
      #mini-table("fx-scores")
      #v(0.3em)
      Point package and read index are hit about as often as the attack's delivery, but they aren't deliveries,
      so they score near zero.
    ],
    [
      #set text(size: 13.5pt)
      #set enum(spacing: 0.75em)
      + *Rank* every action by flow score.
      + *Find each one's group.* Take the rounds in which the action was hit, and trace back through the actions
        the data came through. Keep those that appear in at least #n("sc.keep") of those rounds: their agents are
        the group. Here: the #n("fx.group.a"). A group already found is skipped.
      + *Judge.* The LLM monitor reads each of the top #n("sc.groups") groups together, and flags the fleet if any
        scores #n("sc.threshold") or more.
      #v(0.4em)
      The flow scores only choose what the judge reads; the judge decides. A leak inside one agent is in that
      agent's own transcript, which the per-agent monitor reads, so the flow graph looks only for data that
      crosses agents.
    ],
  )
]

// --- Experiment C: results --------------------------------------------------------------------------------------
#figure-slide("sc-figure")[The flow graph catches every split attack, even where the provenance graph fails.]
#figure-slide("sc-scores")[The judge's scores for attacks and honest fleets never overlap.]

// --- Shortcomings and future work -------------------------------------------------------------------------------
#slide(title: [Shortcomings and future work])[
  #set text(size: 13.5pt)
  #set list(spacing: 0.6em)
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
      - *Data carried in an agent's context.* If one agent writes private data to a file and another reads it and
        emails it, the flow stops at the read: a read writes nothing, so it isn't a carrier.
    ],
    [
      #text(size: 16pt, weight: "bold", fill: blue)[Future work]
      - *Harder honest teams,* such as private data that _is_ authorized for export, so the flow has to follow
        the policy and not just the data.
      - *Live LLM agents and other attacks,* such as sabotage, and attackers who know how the monitor works.
      - *Flows without record names,* using links that Jev judges ("did this action use that one's output?").
      - *A read that shows private data carries it* into the agent's next action, and a sink question that
        covers any action sending data out, such as email.
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
  - A Decision Model constructed graph finds the right agents: it flagged the split attack in #n("sc.split")
    judgments with #n("sc.honest") false alarms, up to #n("sc.agents.n1600") agents, for about #n("sc.usd.base") of labels per
    303-agent fleet.
  #v(1fr)
  #takeaway[To find which agents to read together, follow the data they pass between them.]
]
