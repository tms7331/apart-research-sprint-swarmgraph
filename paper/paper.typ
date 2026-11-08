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
