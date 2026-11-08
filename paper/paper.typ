// The paper. Build it with bin/build-paper (README.md says how to write it). One sentence per line.
// Numbers, tables, figures and prompts come from the ledger by key (build/numbers.md lists them);
// none is typed by hand. Page budget: 8 pages before References, the title block included.
#import "lib.typ": *

#show: apart.with(
  title: [Follow the Data:\ Catching Split Attacks in Agent Swarms],
  authors: (
    (name: [Thomas Redfern], affiliation: [Unaffiliated]),
  ),
  abstract: [
    #todo[the abstract, 150 to 250 words, written last from the final results]
  ],
)

= Introduction
#todo[the question, why it matters, and the contributions]
Splitting a hidden objective across agents can hide it from a monitor that reads one agent at a time @kitaoka2026.

= Methods <sec-methods>
#todo[the transfer mechanism, the five run types, the two monitor views, and the threshold]
Each of the #n("tb.episodes") scripted episodes is judged #n("tb.readings.per.view") time(s) per view, and a team is flagged when its median suspicion score is at least #n("tb.threshold").

= Results <sec-results>
== Reproducing the fragmentation result <sec-step1>
#todo[the reproduction of the fragmentation result, from the full run]
Reading each agent individually, the monitor flags #n("tb.solo.flagged") solo attacks and #n("tb.split.flagged") split attacks; reading each team together, it flags #n("tb.split.joint.flagged") split attacks (@fig-tb).
On honest teams, reading individually gives #n("tb.honest.flagged") false alarms and reading together #n("tb.honest.joint.flagged") (@tab-tb).

#figure(
  data-figure("tb-figure", width: 100%),
  caption: [*Splitting an attack hides it from a monitor that reads each agent individually.* Each row is one team (run #n("tb.run")); its arrow runs from its score read individually (the median for its highest-scoring member) to its score read together (the median for the whole team). Teams right of the dashed threshold are flagged. The honest teams take the same three steps as the attack but ship the shareable file; the incomplete attacks shown are missing their backup step, so nothing private leaves. Solo teams, honest maintenance teams and the other incomplete attacks are in @tab-tb.],
) <fig-tb>
#claim("splitting an attack hides it from a monitor that reads each agent individually", ("tb.split.flagged", "tb.solo.flagged"), (split, solo) => split < solo)

#figure(
  data-table("tb-table"),
  caption: [Median score per episode, read individually (the highest-scoring member) and read together, with each member's median.],
) <tab-tb>

== Hiding the team in a growing fleet <sec-scaling>
We hide the team among up to #n("sa.agents.n180") agents and give an LLM monitor #n("sa.budget") tool calls to search and read the fleet's log (@fig-scaling).
It flags a fleet when its final suspicion score is at least #n("sa.threshold"), and each fleet is monitored #n("sa.passes") times.
At #n("sa.agents.n30") agents it still flags the split attack in #n("sa.split.n30") runs and the solo attack in #n("sa.solo.n30").
At #n("sa.agents.n100") agents it flags the split attack in #n("sa.split.n100"), and at #n("sa.agents.n180") in #n("sa.split.n180").
The solo attack holds out longer: #n("sa.solo.n100"), then #n("sa.solo.n180").
#claim("the solo attack holds out longer than the split attack", ("sa.solo.n100", "sa.split.n100", "sa.solo.n180", "sa.split.n180"), (s1, p1, s2, p2) => s1 > p1 and s2 > p2)
The monitor never flags an honest fleet (#n("sa.honest")), and its highest score on one is #n("sa.honest.max").
#claim("the monitor never flags an honest fleet", ("sa.honest",), h => h == 0)
Every miss is a failure to find the evidence, not to judge it: in #n("sa.misses.saw.all") of #n("sa.misses") missed attacks had the monitor seen every colluder's events, and in #n("sa.catches.saw.all") of #n("sa.catches") catches it had (@tab-scaling).
#claim("no missed attack had seen every colluder's events", ("sa.misses.saw.all",), m => m == 0)
#claim("every catch had seen every colluder's events", ("sa.catches.saw.all", "sa.catches"), (a, b) => a == b)
While the log fits in the budget the monitor simply reads it through: #pct("sa.calls.readlog.fits") of its calls on those fleets read the log in order.
Beyond that it must search (#pct("sa.calls.search.over") of its calls), uses its whole budget, and starts to miss.

#figure(
  data-figure("sa-figure", width: 100%),
  caption: [*Once the log exceeds the monitor's capacity, attacks slip through.* Share of runs that flag the fleet, by fleet size (#n("sa.explorations") runs: each fleet monitored #n("sa.passes") times in each of four layouts). The monitor's capacity is #n("sa.budget") tool calls of at most #n("sa.read.max") events each (#n("sa.capacity") events), whatever the fleet size; right of the dashed line, the log is longer.],
) <fig-scaling>
#claim("once the log exceeds the monitor's capacity, attacks slip through", ("sa.split.n30", "sa.solo.n30", "sa.split.n100", "sa.split.n180"), (s30, o30, s100, s180) => s30 == 1 and o30 == 1 and s100 < 1 and s180 < 1)

#figure(
  data-table("sa-table"),
  caption: [Experiment A by fleet size: attacks caught and honest fleets falsely flagged (out of four layouts × two passes), with the median calls and input tokens per run.],
) <tab-scaling>

== Grouping the log with a provenance graph <sec-graph>
#todo[the graph in a sentence or two: event nodes; call-result, same-agent and shared-record edges; busy records as hubs; union-find chains; and the graph tools]
We give the same monitor a provenance graph of the log, built as in FragBench @mehta2026, and tools to list, search and read its chains, with the same #n("sa.budget") calls.
The fleet stays at #n("sb.agents") agents (#n("sb.teams") honest teams), and we add tool-call overlap between teams: at overlap $N$, each team reads about $N$ records that one other team also reads. The records are listings, so no data passes between the teams, but each shared read links the two teams in the graph.
With no overlap these are the same fleets as in the previous section (#n("sb.same.fleets") of #n("sb.zero.fleets") identical), and the graph helps: the monitor flags the split attack in #n("sb.split.o0") runs, against #n("sa.split.n100") without it.
#claim("the graph helps on the overlap-0 fleets", ("sb.split.o0", "sa.split.n100", "sb.same.fleets", "sb.zero.fleets"), (g, a, s, z) => g > a and s == z)
As overlap grows, the chain that holds the colluders takes in other teams: #n("sb.chain.o0") agents with no overlap, #n("sb.chain.o1") at overlap 1 and #n("sb.chain.o2") at overlap 2 (@fig-graph).
Detection falls with it, from #n("sb.split.o05") at overlap 0.5 to #n("sb.split.o1") at 1, #n("sb.split.o15") at 1.5 and #n("sb.split.o2") at 2.
Whether the monitor finds the attack follows the size of that chain: it flags #n("sb.small.caught") fleets whose colluders' chain is at most #n("sb.small.limit") agents, a tenth of the fleet, and #n("sb.large.caught") of the rest.
#claim("small chains are caught more often than large ones", ("sb.small.caught", "sb.large.caught"), (s, l) => s > l)
At overlap 4 nearly the whole fleet is one chain, and the monitor turns to text search (#pct("sb.calls.search.o4") of its calls, against #pct("sb.calls.search.o0") with no overlap; @fig-tools); it flags #n("sb.split.o4").
As without the graph, every miss is a failure to find the evidence: in #n("sb.misses.saw.all") of #n("sb.misses") missed attacks had the monitor seen all three colluders' events, and in #n("sb.catches.saw.all") of #n("sb.catches") catches it had (@tab-graph).
#claim("no missed attack had seen every colluder's events", ("sb.misses.saw.all",), m => m == 0)
#claim("every catch had seen every colluder's events", ("sb.catches.saw.all", "sb.catches"), (a, b) => a == b)
The monitor never flags an honest fleet (#n("sb.honest")), and its highest score on one is #n("sb.honest.max").
#claim("the graph monitor never flags an honest fleet", ("sb.honest",), h => h == 0)
#todo[each cell is one run per layout, so a difference of one or two (overlap 2 against 4) is within noise; a second pass, as for the monitor without a graph]

#grid(columns: (1fr, 1fr), gutter: 1.2em,
  [#figure(
    data-figure("sb-tools", width: 100%),
    caption: [*As overlap grows, the monitor abandons the graph for text search.* The monitor's tool calls by kind (graph tools list, search and read the graph's chains) at #n("sb.agents") agents, with the split attacks it caught above each bar (#n("sb.explorations") runs: one per layout and run type at each overlap).],
  ) <fig-tools>],
  [#figure(
    data-figure("sb-figure", width: 100%),
    caption: [*The graph helps until overlap merges the fleet into one chain.* Agents in the chain that holds the three colluders, one square per attack fleet, filled where the monitor caught it; shaded, chains of at most a tenth of the fleet. No honest fleet is flagged (#n("sb.honest")).],
  ) <fig-graph>],
)
#claim("as overlap grows, the monitor abandons the graph for text search", ("sb.calls.graph.o0", "sb.calls.graph.o4", "sb.calls.search.o0", "sb.calls.search.o4"), (g0, g4, s0, s4) => g4 < g0 and s4 > s0)
#claim("the graph helps until overlap merges the fleet into one chain", ("sb.split.o0", "sb.split.o2", "sb.small.caught", "sb.large.caught"), (o0, o2, small, large) => o0 > o2 and small > large)

#figure(
  data-table("sb-table"),
  caption: [Experiment B by overlap: the colluders' chain in each layout, attacks caught and honest fleets falsely flagged (out of four layouts), the share of calls that used a graph tool, and the median calls and input tokens per run.],
) <tab-graph>

== Following the data instead of grouping agents <sec-flow>
#todo[the method in full: the three Jev questions, the linking rule, the sampled worlds and the judge reading each group together; why a plain read passes nothing on]
We keep the judge model and threshold, but let a flow graph choose which agents the judge reads together.
Jev, a decision model, labels each tool call with three probabilities: that it touches private data, that it passes data or a reference on into another record, and that it switches on a delivery outside the organization.
Calls are linked where one writes a record that a later one names, and #n("sc.worlds") sampled worlds score where private data reaches an outside delivery through more than one agent.
Step 1's monitor then reads the agents on each of the top #n("sc.groups") paths together, and the fleet is flagged when any of them scores at least #n("sc.threshold").
On B's fleets (#n("sc.same.fleets") of #n("sc.curve.fleets") identical) it flags the split attack in #n("sc.split.curve") judgments, against #n("sc.b.split") runs for B's graph monitor (@fig-flow).
#claim("the flow graph beats B on B's own fleets", ("sc.split.curve", "sc.b.split", "sc.same.fleets", "sc.curve.fleets"), (c, b, s, z) => c > b and s == z)
It keeps flagging past B's range: #n("sc.split.o8") at overlap 8, #n("sc.split.o16") at overlap 16, and #n("sc.split.n1600") in fleets of #n("sc.agents.n1600") agents.
It never flags an honest fleet (#n("sc.honest")).
#claim("the flow graph never flags an honest fleet", ("sc.honest",), h => h == 0)
In every attack judgment the group the judge scores highest is exactly the three colluders (#n("sc.judge.colluders")), and attack fleets score at least #n("sc.judge.attack.min") against at most #n("sc.judge.honest.max") for honest ones (@fig-scores); the two passes agree on #n("sc.agree") fleets (@tab-flow).
#claim("the judge's top group is always the colluders", ("sc.judge.colluders",), c => c == 1)
#claim("attack and honest judge scores don't overlap", ("sc.judge.attack.min", "sc.judge.honest.max"), (a, h) => a > h)
Each group the judge reads is about #n("sc.judge.chars") characters, against #n("sc.log.chars") for the whole log of a 100-team fleet, and labelling costs #n("sc.usd.base") per 100-team fleet and #n("sc.usd.largest") at #n("sc.agents.n1600") agents.
#todo[caveats: question wording tuned on layout 0 at overlap 4; one generator with two kinds of honest team; paths must cross agents, so solo attacks are out of scope; B was not run on the scaling arm]

#figure(
  data-figure("sc-figure", width: 100%),
  caption: [*The flow graph catches every split attack, even where the provenance graph fails.* Split attacks caught under each condition, by method: the monitor without a graph (@fig-scaling), B's graph monitor and the flow graph with Step 1's monitor reading each group together (#n("sc.judgments") judgments: #n("sc.fleets") fleets, each judged #n("sc.passes") times). Hatched, conditions a method wasn't run on.],
) <fig-flow>
#claim("the flow graph catches every split attack, even where the provenance graph fails", ("sc.split", "sc.b.split"), (c, b) => c == 1 and b < 1)

#figure(
  data-figure("sc-scores", width: 100%),
  caption: [*The judge's scores for attacks and honest fleets never overlap.* The judge's score on each of the flow graph's judgments, attack fleet against its honest twin, under each condition; dashed, the flag threshold.],
) <fig-scores>
#claim("the judge's scores for attacks and honest fleets never overlap", ("sc.judge.attack.min", "sc.judge.honest.max", "sc.threshold"), (a, h, t) => a >= t and h < t)

#figure(
  data-table("sc-table"),
  caption: [Experiment C by fleet: split attacks caught by B's graph monitor (its runs) and by the flow graph, honest fleets falsely flagged (out of four layouts × two passes), the range of judge scores, and the Jev labelling cost of one fleet.],
) <tab-flow>

= Discussion and Limitations
#todo[what the result does and does not establish]

= Conclusion
#todo[the main findings in one or two paragraphs]

#unnumbered[Code and Data]
#todo[the repository link, with data in `logs/`]
The paper build (`paper/`) is preexisting work, ported from our earlier Apart hackathon project for the AI Collusion Research Sprint (#link("https://github.com/carver/apart-research-collusion-sprint-2026")[github.com/carver/apart-research-collusion-sprint-2026]).

#unnumbered[LLM Usage Statement]
#todo[how LLMs were used]

#references("refs.bib")

#show: appendix

= Limitations and Dual-Use / Ethical Considerations
#todo[what the result does and does not establish, and any way the setup could make multi-agent attacks easier to carry out or harder to detect]
