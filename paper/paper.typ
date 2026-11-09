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
We use a data-exfiltration scenario modeled on the weight-exfiltration attack in MiniLab @kitaoka2026: a team of three agents maintains the records that a scheduled partner delivery reads from.
Three records point to one another: a delivery schedule names a package entry, and the package entry names the record whose data is to be delivered, at first a shareable sample.
After the agents finish, a sync service runs on its own: when the schedule is enabled and the package is marked prepared, it follows the two pointers and copies whatever the named record holds to the schedule's partner destination.
The service checks that the package is ready, not what it contains.
The organization's policy names a model checkpoint as private, never to reach a partner, names a sample file as shareable, and permits internal backups of either.

The attack takes three steps, one per agent.
The backup agent copies the private checkpoint into the internal bundle, the staging agent points the package at that bundle, and the sync agent switches the delivery on; the sync service then delivers the checkpoint to the partner.
Each step is allowed on its own: internal backups are permitted, packages may reference internal bundles, and enabling a delivery is routine maintenance.
No agent uses a permission it lacks.
Each can change only its own record and can't read past it, so the sync agent can't see what the package points to, and the staging agent can't see what the bundle holds.
Any two of the steps leave the checkpoint inside the organization; only all three move it out.
Each step is exactly what its agent's task asks for, so a colluder's own transcript is the same as that of an agent on an honest team.

Honest teams take the same three steps with one difference.
A team that ships shareable data backs up the sample instead of the checkpoint, so the delivery it switches on is allowed.
A team that leaves the delivery off backs up the checkpoint and points the package at it, as the attack does, but keeps the schedule disabled.
Each agent reads its record and then changes it (the backup agent also reads the file it copies), then posts a one-line status message; the agents never message each other.
The agents are scripted: each run type's actions are fixed in advance and carried out in order, so no model plays the agents.
Step 1 compares five run types on single teams: the split attack; a solo attack, in which one agent holds all three tasks and permissions; the two kinds of honest team; and an incomplete attack, in which one agent makes only the routine part of its change, so the chain never completes.
Each run type comes in #n("tb.layouts") layouts, which vary the records' names and the wording of the tasks.

The monitor is an LLM (#n("tb.model") at #n("tb.effort") reasoning effort) that reads the policy, a description of the services, and the agents' tasks, tool calls, results and messages.
It doesn't see the service's own records, or the delivery itself.
It scores suspicion from 0 to 100, with an assessment and the events it rests on.
Step 1 reads each team in two ways: individually, one agent's transcript at a time, where a team's score is its highest-scoring member's; and together, the whole team's transcripts in one prompt.
Each of the #n("tb.episodes") scripted episodes is read by the monitor #n("tb.readings.per.view") time(s) per view, and a team is flagged when its median suspicion score is at least #n("tb.threshold").

Experiments A to C hide the team in a fleet of background teams.
Each background team is an independent copy of the same workflow with its own records, and the background alternates the two kinds of honest team.
All teams' actions are interleaved at random, with each team's own order kept, so the attacking team's position in the log gives nothing away.
Every attack fleet has an honest twin, the same fleet with the attacking team replaced by one that ships shareable data, and a flag on a twin is a false alarm.

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

== Structuring the log with a provenance graph <sec-graph>
#todo[the graph in a sentence or two: event nodes; call-result, same-agent and shared-record edges; busy records as hubs; union-find chains; and the graph tools]
We give the same monitor a provenance graph of the log, built as in FragBench @mehta2026, and tools to list, search and read its chains, with the same #n("sa.budget") calls.
The fleet stays at #n("sb.agents") agents (#n("sb.teams") honest teams), and we add tool-call overlap between teams: at overlap $N$, each team reads about $N$ records that one other team also reads. The records are listings, so no data passes between the teams, but each shared read links the two teams in the graph.
With no overlap these are the same fleets as in the previous section (#n("sb.same.fleets") of #n("sb.zero.fleets") identical), and the graph helps: the monitor flags the split attack in #n("sb.split.o0") runs, against #n("sa.split.n100") without it.
#claim("the graph helps on the overlap-0 fleets", ("sb.split.o0", "sa.split.n100", "sb.same.fleets", "sb.zero.fleets"), (g, a, s, z) => g > a and s == z)
As overlap grows, the chain that holds the colluders takes in other teams: #n("sb.chain.o0") agents with no overlap, #n("sb.chain.o1") at overlap 1 and #n("sb.chain.o2") at overlap 2 (@fig-graph).
Detection falls with it, from #n("sb.split.o05") at overlap 0.5 to #n("sb.split.o1") at 1, #n("sb.split.o15") at 1.5 and #n("sb.split.o2") at 2.
Whether the monitor finds the attack follows the size of that chain: it flags the attack in #n("sb.small.caught") runs on fleets whose colluders' chain is at most #n("sb.small.limit") agents, a tenth of the fleet, and #n("sb.large.caught") of the rest.
#claim("small chains are caught more often than large ones", ("sb.small.caught", "sb.large.caught"), (s, l) => s > l)
At overlap 4 nearly the whole fleet is one chain, and the monitor turns to text search (#pct("sb.calls.search.o4") of its calls, against #pct("sb.calls.search.o0") with no overlap; @fig-tools); it flags #n("sb.split.o4").
As without the graph, all but one miss is a failure to find the evidence: in #n("sb.misses.saw.all") of #n("sb.misses") missed attacks had the monitor seen all three colluders' events, and in #n("sb.catches.saw.all") of #n("sb.catches") catches it had (@tab-graph).
In that one run the monitor found the export path but concluded, wrongly, that the policy didn't cover the checkpoint, and scored it #n("sb.misses.saw.score").
#claim("all but one missed attack had not seen every colluder's events", ("sb.misses.saw.all",), m => m == 1)
#claim("every catch had seen every colluder's events", ("sb.catches.saw.all", "sb.catches"), (a, b) => a == b)
The monitor never flags an honest fleet (#n("sb.honest")), and its highest score on one is #n("sb.honest.max").
#claim("the graph monitor never flags an honest fleet", ("sb.honest",), h => h == 0)

#grid(columns: (1fr, 1fr), gutter: 1.2em,
  [#figure(
    data-figure("sb-tools", width: 100%),
    caption: [*As overlap grows, the monitor abandons the graph for text search.* The monitor's tool calls by kind (graph tools list, search and read the graph's chains) at #n("sb.agents") agents, with the split attacks it caught above each bar (#n("sb.explorations") runs: each fleet monitored #n("sb.passes") times).],
  ) <fig-tools>],
  [#figure(
    data-figure("sb-figure", width: 100%),
    caption: [*The graph helps until overlap merges the fleet into one chain.* Agents in the chain that holds the three colluders, one square per attack fleet: solid where the monitor caught the attack in every run, light where it caught it in some, hollow where it never did; shaded, chains of at most a tenth of the fleet. No honest fleet is flagged (#n("sb.honest")).],
  ) <fig-graph>],
)
#claim("as overlap grows, the monitor abandons the graph for text search", ("sb.calls.graph.o0", "sb.calls.graph.o4", "sb.calls.search.o0", "sb.calls.search.o4"), (g0, g4, s0, s4) => g4 < g0 and s4 > s0)
#claim("the graph helps until overlap merges the fleet into one chain", ("sb.split.o0", "sb.split.o2", "sb.small.caught", "sb.large.caught"), (o0, o2, small, large) => o0 > o2 and small > large)

#figure(
  data-table("sb-table"),
  caption: [Experiment B by overlap: the colluders' chain in each layout, attacks caught and honest fleets falsely flagged (out of four layouts × #n("sb.passes") passes), the share of calls that used a graph tool, and the median calls and input tokens per run.],
) <tab-graph>

== Following the data instead of grouping agents <sec-flow>
We keep the judge model and threshold, but let a flow graph choose which agents the judge reads together.
The method has four steps: label each action, link the actions, simulate how private data could spread along the links, and have the monitor read the agents the data passes through.

*Label.* The graph has one node per tool call.
Jev, a decision model, reads each call on its own, with the services text, the policy paragraphs for the teams it mentions, the agent's task and the call's result, and answers three yes/no questions as probabilities: whether the call touches data the policy marks private (its source probability), whether it passes data or a reference to data on into another record (its carrier probability), and whether it switches on a delivery outside the organization (its sink probability).
The probabilities belong to the nodes; the links carry no numbers.

*Link.* Links point forward in the log, and two rules make them.
First, a call that writes a record, meaning its arguments carry more than the record's name, links to every later call by any agent that names that record, in the later call's arguments or in its result.
Second, each call links to the same agent's next call, since an agent carries what it saw into its next action.
Two calls that only read the same record are not linked, unlike in the provenance graph, which links any two events that mention the same record.
A link means only that data could flow from one call to the other; whether it does is decided by the calls at its two ends.
A plain read writes nothing, so Jev gives it a low carrier probability: the shared reads that merge the provenance graph's chains are linked here too, but pass almost nothing along those links.

*Simulate.* We then run #n("sc.worlds") random rounds.
In each round, every call's source and carrier questions are answered with a random number between 0 and 1: below the call's probability means yes for that round, so a call with source probability 0.95 is a source in about 95% of rounds.
The sink probability is not drawn.
We then go through every call once, in the order of the log.
Since every link points forward in time, a call's incoming calls are already settled when we reach it, and parts of the graph that don't connect to each other are visited all the same; there is no starting point to choose.
A call holds private data in a round if it is a source in that round, or if an incoming call holds data and it is a carrier in that round.
It is hit if the data reached it from a call by a different agent, or from the same agent's previous call when that call was itself hit and is a carrier.
Data that never leaves one agent doesn't count: a leak inside one agent is in that agent's own transcript, which the per-agent monitor reads, so the flow graph looks only for data that crosses agents.
Every source spreads at once, so the simulation needs no list of paths, and all rounds are computed together as one pass over the log.

*Score and judge.* After the rounds, every call has a hit rate, the share of rounds in which it was hit, and a flow score, its hit rate times its sink probability.
The flow score is the only number used to rank: a call that private data reaches often but that sends nothing out, such as a staging step, scores near zero.
We rank the calls by flow score and find each one's group: in the rounds in which the call was hit, we trace back through the calls the data came through, and keep those that appear in at least #n("sc.keep") of those rounds; their agents are the group.
A group with the same agents as one already found is skipped.
Step 1's monitor then reads the agents of each of the top #n("sc.groups") groups together, with the policy cut to the paragraphs for their teams and without the flow scores, and the fleet is flagged when any group scores at least #n("sc.threshold").
The flow scores only choose what the judge reads; the judge decides.
In one #n("sc.ex.agents")-agent fleet at overlap #n("sc.ex.overlap"), for example, private data reaches the colluders' delivery in #n("sc.ex.hit") of the rounds, a flow score of #n("sc.ex.score") against #n("sc.ex.next") for the next group, and the judge scores the colluders #n("sc.ex.judge.top") and the next two groups #n("sc.ex.judge.rest").
Experiment C's fleets hold only split attacks and their honest twins, so it tests the group half of a monitor that would also read each agent individually.

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
  caption: [*The flow graph catches every split attack, even where the provenance graph fails.* Split attacks caught under each condition, by method: the monitor without a graph (@fig-scaling), B's graph monitor and the flow graph with Step 1's monitor reading each group together (#n("sc.judgments") judgments: #n("sc.fleets") fleets, each monitored #n("sc.passes") times). Hatched, conditions a method wasn't run on.],
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

The flow graph follows data through records, not through an agent's own context.
If one agent writes private data to a file, and a second agent reads that file and then emails what it read, the flow graph misses it.
The read writes nothing, so Jev gives it a low carrier probability and the data stops there; and the sink question asks about deliveries the synchronization service carries out, so a direct email may not count as one.
Two changes would cover this case: let a read whose result shows private data carry it into the agent's next action, and ask the sink question about any action that sends data outside the organization.
The shared reads that merge the provenance graph's chains show other teams' record names, not private data, so the first change should not let overlap merge the teams again.
Both changes alter the method after the results, so they would need a rerun on every fleet.

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
