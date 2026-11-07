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
