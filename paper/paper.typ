// The paper. Build it with bin/build-paper (README.md says how to write it). One sentence per line.
// Numbers, tables, figures and prompts come from the ledger by key (build/numbers.md lists them);
// none is typed by hand. Page budget: 8 pages before References, the title block included.
#import "lib.typ": *

#show: apart.with(
  title: [Who Should a Monitor Read Together?],
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
The per-agent monitor flags #n("tb.solo.flagged") solo attacks and #n("tb.split.flagged") split attacks, and the joint monitor flags #n("tb.split.joint.flagged") split attacks (@fig-tb).
On honest teams, the per-agent monitor gives #n("tb.honest.flagged") false alarms and the joint monitor #n("tb.honest.joint.flagged") (@tab-tb).

#figure(
  data-figure("tb-figure", width: 100%),
  caption: [Median suspicion score of each team, by run type and monitor, from run #n("tb.run"). Teams at or above the dashed threshold are flagged.],
) <fig-tb>

#figure(
  data-table("tb-table"),
  caption: [Median score of each monitor view, per episode.],
) <tab-tb>

== Hiding the team in a growing fleet <sec-scaling>
We hide the team among up to #n("sa.agents.n180") agents and give an LLM explorer #n("sa.budget") tool calls to search and read the fleet's log (@fig-scaling).
It flags a fleet when its final suspicion score is at least #n("sa.threshold"), and each fleet is explored #n("sa.passes") times.
At #n("sa.agents.n30") agents it still flags the split attack in #n("sa.split.n30") explorations and the solo attack in #n("sa.solo.n30").
At #n("sa.agents.n100") agents it flags the split attack in #n("sa.split.n100"), and at #n("sa.agents.n180") in #n("sa.split.n180").
The solo attack holds out longer: #n("sa.solo.n100"), then #n("sa.solo.n180").
#claim("the solo attack holds out longer than the split attack", ("sa.solo.n100", "sa.split.n100", "sa.solo.n180", "sa.split.n180"), (s1, p1, s2, p2) => s1 > p1 and s2 > p2)
The explorer never flags an honest fleet (#n("sa.honest")), and its highest score on one is #n("sa.honest.max").
#claim("the explorer never flags an honest fleet", ("sa.honest",), h => h == 0)
Every miss is a failure to find the evidence, not to judge it: in #n("sa.misses.saw.all") of #n("sa.misses") missed attacks had the explorer seen every colluder's events, and in #n("sa.catches.saw.all") of #n("sa.catches") catches it had (@tab-scaling).
#claim("no missed attack had seen every colluder's events", ("sa.misses.saw.all",), m => m == 0)
#claim("every catch had seen every colluder's events", ("sa.catches.saw.all", "sa.catches"), (a, b) => a == b)
While the log fits in the budget the explorer simply reads it through: #pct("sa.calls.readlog.fits") of its calls on those fleets read the log in order.
Beyond that it must search (#pct("sa.calls.search.over") of its calls), uses its whole budget, and starts to miss.

#figure(
  data-figure("sa-figure", width: 100%),
  caption: [Share of explorations that flag the fleet, by fleet size (#n("sa.explorations") explorations: each fleet explored #n("sa.passes") times in each of four layouts). The explorer has #n("sa.budget") tool calls whatever the fleet size. Right of the dashed line, its log is longer than it can read within that budget.],
) <fig-scaling>

#figure(
  data-table("sa-table"),
  caption: [Experiment A by fleet size: attacks caught and honest fleets falsely flagged (out of four layouts × two passes), with the median calls and input tokens per exploration.],
) <tab-scaling>

== Grouping the log with a provenance graph <sec-graph>
#todo[the graph in a sentence or two: event nodes; call-result, same-agent and shared-record edges; busy records as hubs; union-find chains; and the graph tools]
We give the same explorer a provenance graph of the log, built as in FragBench @mehta2026, and tools to list, search and read its chains, with the same #n("sa.budget") calls.
The fleet stays at #n("sb.agents") agents (#n("sb.teams") honest teams), and we add cross-team overlap: shared indexes, each listing two teams' staging records, that a member of each team reads.
With no overlap these are the same fleets as in the previous section (#n("sb.same.fleets") of #n("sb.zero.fleets") identical), and the graph helps: the explorer flags the split attack in #n("sb.split.o0") explorations, against #n("sa.split.n100") without it.
#claim("the graph helps on the overlap-0 fleets", ("sb.split.o0", "sa.split.n100", "sb.same.fleets", "sb.zero.fleets"), (g, a, s, z) => g > a and s == z)
As overlap grows, the chain that holds the colluders takes in other teams: #n("sb.chain.o0") agents with no overlap, #n("sb.chain.o1") at overlap 1 and #n("sb.chain.o2") at overlap 2 (@fig-graph).
Detection falls with it, from #n("sb.split.o05") at overlap 0.5 to #n("sb.split.o1") at 1, #n("sb.split.o15") at 1.5 and #n("sb.split.o2") at 2.
Whether the explorer finds the attack follows the size of that chain: it flags #n("sb.small.caught") fleets whose colluders' chain is at most #n("sb.small.limit") agents, a tenth of the fleet, and #n("sb.large.caught") of the rest.
#claim("small chains are caught more often than large ones", ("sb.small.caught", "sb.large.caught"), (s, l) => s > l)
At overlap 4 nearly the whole fleet is one chain, and the explorer turns to text search (#pct("sb.calls.search.o4") of its calls, against #pct("sb.calls.search.o0") with no overlap); it flags #n("sb.split.o4").
As without the graph, every miss is a failure to find the evidence: in #n("sb.misses.saw.all") of #n("sb.misses") missed attacks had the explorer seen all three colluders' events, and in #n("sb.catches.saw.all") of #n("sb.catches") catches it had (@tab-graph).
#claim("no missed attack had seen every colluder's events", ("sb.misses.saw.all",), m => m == 0)
#claim("every catch had seen every colluder's events", ("sb.catches.saw.all", "sb.catches"), (a, b) => a == b)
The explorer never flags an honest fleet (#n("sb.honest")), and its highest score on one is #n("sb.honest.max").
#claim("the graph explorer never flags an honest fleet", ("sb.honest",), h => h == 0)
#todo[each cell is one exploration per layout, so a difference of one or two (overlap 2 against 4) is within noise; a second pass, as for the explorer without a graph]

#figure(
  data-figure("sb-figure", width: 100%),
  caption: [Experiment B: #n("sb.agents") agents, as cross-team overlap grows (#n("sb.explorations") explorations, one per layout and run type at each overlap). Left: share of explorations that flag the fleet; the grey diamond is the explorer without a graph on the same overlap-0 fleets (@fig-scaling). Right: agents in the chain that holds the three colluders, one square per attack fleet, filled where the explorer caught it.],
) <fig-graph>

#figure(
  data-table("sb-table"),
  caption: [Experiment B by overlap: the colluders' chain in each layout, attacks caught and honest fleets falsely flagged (out of four layouts), the share of calls that used a graph tool, and the median calls and input tokens per exploration.],
) <tab-graph>

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
