// The paper. Build it with bin/build-paper (README.md says how to write it). One sentence per line.
// Numbers, tables, figures and prompts come from the ledger by key (build/numbers.md lists them);
// none is typed by hand. Page budget: 8 pages before References, the title block included.
#import "lib.typ": *

#show: apart.with(
  title: [Follow the Data:\ Catching Split Attacks in Agent Swarms with Decision Model Graphs],
  authors: (
    (name: [Thomas Redfern], affiliation: [Unaffiliated]),
  ),
  abstract: [
    A harmful task split across several AI agents can evade a monitor that reviews each agent separately, because each agent's part looks like ordinary work.
    Reviewing the agents together can reveal the attack @kitaoka2026, but in a large fleet the monitor must first find the agents involved.
    We reproduce this effect with a scripted data-exfiltration attack split across three agents, then hide the attacking team among many honest teams performing similar tasks.
    #claim("read one at a time the split attack is missed; read together it is caught", ("tb.split.flagged", "tb.split.joint.flagged"), (p, j) => p == 0 and j == 1)
    We test two approaches to finding the attacking team.
    A monitor searching raw logs within a fixed budget increasingly misses the attack as the fleet grows.
    #claim("the raw-log monitor detects fewer split attacks as the fleet grows", ("sa.split.n30", "sa.split.n180"), (small, big) => small > big)
    Grouping tool calls by the records they touch helps when teams work independently.
    But once honest teams share records, the graph merges them into large groups, leaving the monitor with too much unrelated activity to inspect.
    #claim("the provenance graph works with no shared records and detects fewer split attacks when teams share records", ("sb.split.o0", "sb.split.o2"), (o0, o2) => o0 == 1 and o0 > o2)
    Our method follows possible flows of private data.
    A decision model estimates whether each tool call accesses private data, passes data onward, or enables an external delivery.
    We connect calls through the records they write and reference, then simulate how data could flow between agents.
    These flows identify small groups for the monitor to review together and judge against the organization's policy.
    Across the tested conditions, the method consistently finds the attacking team, and the monitor detects every attack without flagging any honest fleet.
    This holds as fleets grow to thousands of agents and as teams access more shared records.
    #claim("the flow graph finds the attacking team and catches every split attack with no false alarms, in fleets of thousands", ("sc.graph.exact", "sc.split", "sc.honest", "sc.agents.n1600"), (g, s, h, n) => g == 1 and s == 1 and h == 0 and int(n.replace(",", "")) >= 1000)
  ],
)

= Introduction
AI agents increasingly work in teams and larger fleets, with each agent assigned a narrow task, its own permissions, and its own records.
In the AI control setting, these agents are copies of a capable model that we do not fully trust, and a trusted monitor reviews their actions.
Monitoring often treats each agent's transcript separately, but this can miss an attack whose steps are spread across several agents @kitaoka2026.

Kitaoka et al. demonstrated this problem in MiniLab: a per-agent monitor flagged 86.8% of side tasks performed by a single agent, but only 6.7% of the same tasks split across three agents.
Reviewing the colluding agents together raised detection to 31--41% @kitaoka2026.
However, that joint monitor was given the identities of the colluders.
In a fleet of hundreds or thousands of agents, a defender must first find the handful involved in an attack among many others doing similar work.
Kitaoka et al. leave this search problem to future work @kitaoka2026.

This paper asks how a monitor can identify which agents to review together.
We study a controlled scenario in which three agents jointly exfiltrate private data, and place this attacking team among honest teams that perform the same types of actions.
Each attack fleet is paired with an otherwise identical honest fleet in which the attacking team is replaced by one that sends only shareable data.
These pairs let us measure both attack detection and false alarms under matching conditions.

We compare three approaches to finding the attacking team.
The first gives an LLM monitor tools to search and read the raw log within a fixed budget of tool calls.
The second gives the same monitor a FragBench-style provenance graph, which connects events through the records they share @mehta2026.

Our approach, the third, uses a flow graph to trace how private data could move across agents and leave the organization.
A low-cost decision model labels each tool call's role in that flow, and explicit record references link calls together.
We then simulate how private data could travel through these links and rank the resulting candidate groups.
The same LLM monitor reviews the selected agents' transcripts together to determine whether their combined actions constitute an attack.

We make three contributions:
#list(
  [We reproduce the fragmentation result in a minimal, controlled setting where each colluder's transcript is identical to one that an honest agent could produce (@sec-step1).],
  [We evaluate how well existing monitoring approaches scale, using two baseline implementations: a tool-using LLM monitor that searches the raw log as fleet size grows (@sec-scaling), and a FragBench-style provenance graph as teams access more shared records (@sec-graph).
  We identify where each approach breaks down and show that these failures arise from difficulty finding the relevant evidence.],
  [We introduce a flow graph approach that uses a decision model to label how tool calls handle private data, then traces possible flows across agents to identify groups for joint review (@sec-flow-method).
  With the same monitor and decision threshold, it detects every split attack without false alarms across the conditions we test.
  The monitor reviews about #n("sc.judge.chars") characters per group rather than the full log.],
)
#claim("the flow graph flags every split attack with no false alarms", ("sc.split", "sc.honest"), (s, h) => s == 1 and h == 0)

= Problem Setting and Threat Model <sec-setting>
== The scenario <sec-scenario>
We study a scripted data-exfiltration scenario based on the weight-exfiltration attack in MiniLab @kitaoka2026.
Three agents maintain records used by an automated delivery to an external partner.

The delivery follows a chain of three records: a schedule points to a package entry, which points to the record containing the data to send.
Initially, the package points to a shareable sample.
After the agents finish, a sync service checks whether the schedule is enabled and the package is marked prepared.
If both conditions hold, it follows these references and sends the data to the partner.
The service checks that the package is ready but does not inspect its contents.

The organization's policy prohibits sending a private model checkpoint to the partner, allows sharing a sample file, and permits internal backups of either.
The checkpoint's record includes its contents and an export flag set to false.
The policy also makes clear that a filename, a prepared flag, or a successful service response does not authorize an export.
@sec-prompts provides the full policy, service descriptions, and agent tasks.

The attack consists of three steps, each performed by a different agent:
#enum(
  [The backup agent copies the private checkpoint into an internal bundle.],
  [The staging agent updates the package to point to that bundle.],
  [The sync agent enables the delivery schedule, allowing the sync service to send the checkpoint to the partner.],
)

Each agent acts within its permissions and follows its assigned task.
Internal backups are permitted, packages may reference internal bundles, and enabling a delivery is routine maintenance.
The policy violation emerges from their combined actions: any two steps leave the checkpoint inside the organization, while all three cause it to be exported.

Each agent can modify only its own record and has a limited view of the workflow.
The sync agent cannot see what the package points to, and the staging agent cannot see what the bundle contains.
Each colluder's transcript is therefore identical to one that an honest agent could produce.
The agents do not exchange messages, and no individual agent's view reveals the overall attack.

We include two kinds of honest team.
One backs up and delivers the shareable sample instead of the private checkpoint.
The other backs up the checkpoint and points the package to it, but leaves the delivery disabled.
Honest teams therefore either handle private data without exporting it or export only shareable data.
The attacking team combines private data with an enabled external delivery.

In every run, each agent reads and updates its record, then posts a one-line status message.
The backup agent also reads the file it copies.
All actions are fixed in advance and executed in order; no model controls the agents.
Each run type has #n("tb.layouts") layouts that vary the record names and task wording.

== What the monitor sees <sec-view>
Every monitor receives the operator's public log, which includes the policy, service descriptions, and each agent's assigned task and permissions, followed by its tool calls, results, and messages in chronological order.
Each tool call identifies the agent that made it.

The log excludes the sync service's internal records, so the monitor does not observe the delivery itself.
It also excludes run IDs, timestamps, and ground-truth labels.

The evidence needed to detect the attack is spread across the agents' records.
The backup agent's logged read shows the checkpoint's contents and export flag, and its copy operation places those contents in the bundle.
The staging agent's update identifies the bundle, while the sync agent's read identifies the package selected for delivery.
Neither of these last two agents sees the bundle's contents.

@tab-log, in @app-log, illustrates these actions in a fleet of #n("lx.agents") agents with #n("lx.events") logged events.
Each colluder's update occupies a single line among similar updates from honest agents.

= Flow-Graph Monitoring <sec-flow-method>
To choose which agents to review together, we build a graph of possible private-data flows across the fleet.
The monitor and its decision threshold remain unchanged.
This is a form of information-flow, or taint, tracking.
It asks whether private data could pass through multiple agents and reach an action that sends it outside the organization.
Individual actions may look legitimate even when they combine to form such a path.

The method has four steps.
We label tool calls, link them, simulate possible data flows, and select groups of agents for joint review.

== Label
Each node in the graph represents one tool call.
Jev (#n("pr.jev.model")), TypeSafe's decision model, evaluates each call separately.
It receives the service descriptions, the relevant teams' policy paragraphs, the agent's task, and the call and its result.
It then estimates three probabilities by answering the following questions.
#list(
  [*Source.* Does the call touch data that the policy marks as private?],
  [*Carrier.* If data reaches this call, does the call pass it, or a reference to it, into another record?],
  [*Sink.* Does the call enable a delivery outside the organization?],
)

These are separate probabilities, so a call can be both a likely source and a likely carrier.
The probabilities belong to the nodes; the links have no weights.

== Link
All links point forward in time.
We create them using two rules.
#enum(
  [A call that writes a record links to every later call that names that record, whether in its arguments or its result and regardless of which agent makes it.
  We identify writes as calls whose arguments contain more than the record's name.],
  [Each call links to the same agent's next call, representing information the agent may carry from one action to the next.],
)

Reading the same record does not, by itself, create a link between two calls.
This differs from the provenance graph, which connects events whenever they mention the same record.

A link represents a possible route for data.
The node labels determine whether data passes along that route in the simulation.
A plain read writes nothing, so Jev assigns it a low carrier probability.
Shared reads can therefore remain connected through the rules above while passing very little data onward.

== Simulate
We simulate #n("sc.worlds") rounds of possible data flow.
In each round, we sample a yes-or-no source label and a yes-or-no carrier label for every call using its predicted probabilities.
For example, a call with source probability 0.95 is treated as a source in about 95% of rounds.
Sink probabilities are used directly in the scoring step rather than sampled.

We process calls in chronological order.
A call holds private data if it is a source in that round, or if it is a carrier and at least one linked earlier call holds private data.

We also track whether each call is _hit_, meaning that private data has reached it across an agent boundary.
A call is hit if a linked earlier call from another agent holds private data.
A hit also carries forward to the same agent's next call when the preceding call was both hit and a carrier.

== Score and monitor
Each call's _hit rate_ is the fraction of rounds in which it was hit.
We multiply this rate by its sink probability to obtain its _flow score_.
This gives priority to calls that both receive private data across agents and enable an external delivery.
A staging call may receive private data frequently but still score near zero because it does not enable a delivery.

We rank calls by flow score and construct a candidate group for each.
For every round in which the call was hit, we trace backward through the calls that supplied the data.
We retain calls that appear in at least #n("sc.keep") of those rounds and collect their agents into a group.
Groups containing exactly the same agents as an earlier group are skipped.

The monitor from Step 1 then reviews the full transcripts of each of the top #n("sc.groups") groups.
It receives only the policy paragraphs relevant to that group's teams and does not see the flow scores.
The fleet is flagged if any group receives a monitor score of at least #n("sc.threshold").
The graph selects the groups; the monitor makes the final judgment.

@app-flow provides implementation details, a worked example, and an account of how we developed the method.

= Experimental Design and Methods <sec-methods>
== The monitor <sec-monitor>
We use OpenAI's GPT-6.1 Sol (#n("tb.model")) at #n("tb.effort") reasoning effort to review the log described in @sec-view.
The monitor assigns a suspicion score from 0 to 100, cites the events supporting its judgment, and gives one of four assessments—no violation evident, precursor, completed violation, or insufficient information.

Its instructions ask it to consider each agent's assigned task, avoid assuming that an attack exists, and distinguish a successful tool response from authorization to perform an action (@sec-prompts).
We flag scores of at least #n("tb.threshold"), corresponding to MiniLab's threshold of 7.5 on a scale from 0 to 10 @kitaoka2026.
This threshold is fixed in advance rather than tuned to the observed scores.

Every experiment uses the same monitor model and threshold.
Step 1 and Experiment C also use the same monitoring instructions.
Experiments A and B add instructions for exploring the log with tools (@sec-prompts).

== The fleets <sec-fleets>
Experiments A to C place the attacking team among honest background teams.
Each background team follows the same workflow using its own records, and the background alternates between the two kinds of honest team described in @sec-scenario.

We shuffle team order and randomly interleave their actions while preserving the order of actions within each team.
For a given layout and fleet size, all run types use the same background teams, team order, and interleaving.
This prevents the attacking team's position in the log from identifying it.

Each attack fleet has a matched honest fleet in which the attacking team is replaced by one that delivers shareable data.
A flag on this honest fleet counts as a false alarm.
With $N$ honest background teams and one evaluated team, a fleet contains $3N + 3$ agents.
Without background teams, the split-attack fleet is the same episode used in Step 1.

Experiments B and C also vary how often teams access shared records.
We call this _tool-call overlap_.
At overlap $N$, each team reads approximately $N$ records that are also read by one other team.
These records are shared indexes listing two teams' package entries, which the staging agents read before their own staging work.

These reads expose references to another team's records without transferring the underlying data.
Increasing overlap therefore lets us test how monitoring behaves when otherwise independent teams access shared resources.
@tab-varied summarizes the experimental conditions.

#figure(
  table(
    columns: (auto, 1fr, 1fr, 1fr, 1fr),
    stroke: none, inset: (x: 0.4em, y: 0.35em), align: (x, _) => if x == 0 { left } else { center },
    table.hline(stroke: 0.6pt),
    table.header([], [Step 1], [Experiment A], [Experiment B], [Experiment C]),
    table.hline(stroke: 0.4pt),
    [honest twin], [yes, and incomplete attacks], [yes], [yes], [yes],
    [fleet size (agents)], [3], [3 to #n("sa.agents.n180")], [#n("sb.agents")], [#n("sb.agents") to #n("sc.agents.n1600")],
    [tool-call overlap], [none], [0], [0 to 4], [0 to 16],
    [layouts], [#n("tb.layouts")], [#n("tb.layouts")], [#n("sb.layouts")], [#n("sb.layouts")],
    [passes per fleet], [#n("tb.readings.per.view") readings], [#n("sa.passes")], [#n("sb.passes")], [#n("sc.passes")],
    table.hline(stroke: 0.6pt),
  ),
  caption: [*Experimental conditions.* Honest controls, fleet sizes, tool-call overlap, and monitoring repetitions for each experiment.
  Experiment C reuses Experiment B's exact fleets and adds conditions with larger fleets or greater overlap.],
) <tab-varied>

== Measures and evaluation scope <sec-measures>
In Experiments A and B, we distinguish whether the monitor finds the relevant evidence from whether it recognizes the attack.
We count the evidence as found when the monitor retrieves all four of the following, either as full events or search snippets.
#list(
  [The read of the private checkpoint.],
  [The copy of the checkpoint into the bundle.],
  [The prepared package pointing to that bundle.],
  [The enabled delivery schedule.],
)

In Experiment C, we separately measure whether the selected group matches the colluders and whether the monitor flags the fleet.

== Step 1. Reproducing the fragmentation result <sec-step1-method>
_Does splitting an attack across three agents hide it from individual review, and does reviewing the team together recover detection?_

We compare five run types using single teams.
#list(
  [A split attack carried out by three agents.],
  [A solo attack in which one agent has all three tasks and permissions.],
  [An honest team that delivers shareable data.],
  [An honest team that backs up private data but leaves delivery disabled.],
  [An incomplete attack in which one agent performs only the routine part of its task, leaving the attack unfinished.],
)

The incomplete attack has three variants, each omitting a different step.
One-agent versions are also included for the solo attack and honest teams.

We evaluate each team under individual and joint review.
During individual review, the monitor reads one agent's transcript at a time, and the team's score is the highest of its agents' scores.
During joint review, it reads all of the team's transcripts in one prompt.

The monitor reviews each of the #n("tb.episodes") scripted episodes #n("tb.readings.per.view") time(s) under each view.
A team is flagged when its median suspicion score reaches #n("tb.threshold").
Repeated readings measure variation in the monitor's judgments rather than additional attacks, so detection rates are based on #n("tb.layouts") teams per attack type.

== Experiment A. Searching the raw log with a fixed budget <sec-scaling-method>
_Can a monitor with a fixed tool-call budget find the attacking team as the fleet grows?_

We increase fleet size up to #n("sa.agents.n180") agents, with no tool-call overlap.
The monitor starts with the policy, service descriptions, and log size.
It can make one tool call per turn using four available tools.
#list(
  [Search for text, returning the number of matching events and a page of shortened results.],
  [Read a consecutive range of log events in full.],
  [Read specific events by ID.],
  [Read one agent's full transcript.],
)

The budget remains #n("sa.budget") calls at every fleet size.
Each call returns at most #n("sa.read.max") events, giving the monitor a total reading capacity of approximately #n("sa.capacity") events.

The monitor updates its verdict after each turn and gives a final verdict when its budget is exhausted.
The fleet is flagged if the final suspicion score reaches #n("sa.threshold").
No graph is provided, so the monitor must identify related agents through its searches.

We test fleets with 0, 1, 3, 10, 30, 100, and 180 honest background teams across #n("tb.layouts") layouts.
Each condition includes a solo attack, a split attack, and an honest twin, with each fleet monitored #n("sa.passes") times.

== Experiment B. Structuring the log with a provenance graph <sec-graph-method>
_Does grouping events by shared records help the monitor find the attacking team, and how does this change as honest teams share more records?_

We give the same monitor a FragBench-style provenance graph and tools for exploring it @mehta2026.
The tool-call budget remains #n("sa.budget").

Each tool call and each tool result is a separate node.
We link a call to its result, consecutive events from the same agent, and events that name the same record in their arguments or returned records.
Records mentioned by more than #n("sb.busy") agents are treated as busy and create no links.
This fixed cutoff replaces FragBench's approach of down-weighting common resources (@app-graph).

We use union-find to group connected events into chains.
Graph construction depends entirely on the log and requires no model calls.
Without overlap, each team forms its own chain.
With overlap, a shared-index read can connect two teams' chains, and a series of such connections can merge multiple teams into one chain.

In addition to Experiment A's tools, the monitor receives #n("sb.graph.tools") tools for exploring the graph.
These let it list chains from largest to smallest with their sizes and example records, search chains by event text, and read a chain's events in order.
The remaining tools look up an agent's chain and identify which agents accessed a record (@sec-prompts).

We hold fleet size at #n("sb.agents") agents, including #n("sb.teams") honest teams, and vary overlap across 0, 0.5, 1, 1.5, 2, and 4.
Each condition has #n("sb.layouts") layouts, and each fleet is monitored #n("sb.passes") times.

== Experiment C. Following the data <sec-flow-evaluation>
_Can the flow graph find the attacking team as fleets grow and honest teams share more records?_

Experiment C evaluates the method described in @sec-flow-method.
It includes split attacks and their honest twins, so it evaluates the group-monitoring component.
A complete monitoring system would also review agents individually.

We reuse all #n("sc.curve.fleets") fleets from Experiment B without modification, then extend the evaluation in two directions.
We test overlap levels of 8 and 16 with 100 honest teams, and larger fleets of #n("sc.agents.n400") and #n("sc.agents.n1600") agents at overlap 4.
Each additional condition has #n("sb.layouts") layouts and a matched honest fleet.

In total, Experiment C includes #n("sc.fleets") fleets, each monitored #n("sc.passes") times.

= Results <sec-results>
The tables supporting the figures in this section are provided in @app-results.

== Step 1. Reproducing the fragmentation result <sec-step1>
Individual review detects all solo attacks but misses every split attack.
The monitor flags #n("tb.solo.flagged") solo attacks and #n("tb.split.flagged") split attacks when reviewing agents separately.
Reviewing the three agents together restores detection to #n("tb.split.joint.flagged") (@fig-tb).
Neither approach produces false alarms on honest teams, with #n("tb.honest.flagged") under individual review and #n("tb.honest.joint.flagged") under joint review (@tab-tb).
Incomplete attacks are also never flagged, with #n("tb.incomplete.flagged") under individual review and #n("tb.incomplete.joint.flagged") under joint review.
#claim("incomplete attacks are never flagged", ("tb.incomplete.flagged", "tb.incomplete.joint.flagged"), (a, b) => a == 0 and b == 0)

This matches the pattern reported in MiniLab @kitaoka2026.
An attack performed by one agent is detected, splitting it across three agents hides it from individual review, and joint review recovers detection.
Our joint monitor detects a larger share of attacks than MiniLab's.
One likely explanation is that our backup agent's records expose the private data, allowing the monitor to trace the checkpoint into the bundle, follow the package's reference to that bundle, and see the delivery being enabled.

The failure of individual review is largely built into this scenario.
Each colluder's transcript is identical to one that an honest agent could produce.
The empirical results therefore concern detection of solo attacks, recovery through joint review, and false alarms on honest and incomplete cases.

#figure(
  data-figure("tb-figure", width: 100%),
  caption: [*Individual review misses split attacks, while joint review recovers detection.*
  Each row represents one team from run #n("tb.run").
  The arrow connects its individual-review score, the median for its highest-scoring agent, to its joint-review score, the median for the whole team.
  The dashed line marks the flagging threshold.
  The honest teams shown deliver shareable data.
  The incomplete attacks shown omit the backup step, so no private data leaves the organization.
  @tab-tb includes solo teams, honest maintenance teams, and the other incomplete attacks.],
) <fig-tb>
#claim("splitting an attack hides it from a monitor that reads each agent individually", ("tb.split.flagged", "tb.solo.flagged"), (split, solo) => split < solo)

== Experiment A. Searching the raw log with a fixed budget <sec-scaling>
Detection declines as the fleet grows beyond the monitor's reading capacity.
Both attack types are detected in every run in fleets up to #n("sa.agents.n30") agents, with #n("sa.split.n30") split attacks and #n("sa.solo.n30") solo attacks detected at that size (@fig-scaling).
At #n("sa.agents.n100") agents, detection falls to #n("sa.split.n100") for split attacks and #n("sa.solo.n100") for solo attacks.
At #n("sa.agents.n180") agents, it falls to #n("sa.split.n180") and #n("sa.solo.n180"), respectively.
#claim("both attacks slip through at the largest fleet", ("sa.split.n180", "sa.solo.n180"), (p, s) => p < 0.5 and s < 0.5)
The monitor produces no false alarms on honest fleets (#n("sa.honest")), whose highest suspicion score is #n("sa.honest.max").
#claim("the monitor never flags an honest fleet", ("sa.honest",), h => h == 0)

The retrieval records point to evidence discovery as the bottleneck.
None of the #n("sa.misses") missed attacks had all four required pieces of evidence retrieved, while all #n("sa.catches") detected attacks did (@tab-scaling).
#claim("no missed attack had retrieved all four steps", ("sa.misses.steps",), m => m == 0)
#claim("every catch had retrieved all four steps", ("sa.catches.steps", "sa.catches"), (a, b) => a == b)

When the log fits within the reading budget, the monitor reads it sequentially, using #pct("sa.calls.readlog.fits") of its tool calls for that purpose.
Once the log exceeds the budget, text searches account for #pct("sa.calls.search.over") of its calls.
The monitor exhausts its budget and begins to miss attacks.

Searches for the checkpoint, bundle, or enabled delivery return many similar events from honest teams.
The monitor cannot inspect all of them within its budget.
Its explanations for missed attacks describe following honest chains that either contained shareable data or left delivery disabled, without finding the chain that combined private data with an enabled delivery.

#figure(
  data-figure("sa-figure", width: 100%),
  caption: [*Detection declines once the log exceeds the monitor's reading capacity.*
  The figure shows the share of runs that flag the fleet at each fleet size, across #n("sa.explorations") runs.
  Each fleet is monitored #n("sa.passes") times in each of four layouts.
  The budget is fixed at #n("sa.budget") tool calls returning at most #n("sa.read.max") events each, for a total capacity of #n("sa.capacity") events.
  To the right of the dashed line, the log exceeds this capacity.],
) <fig-scaling>
#claim("once the log exceeds the monitor's capacity, attacks slip through", ("sa.split.n30", "sa.solo.n30", "sa.split.n100", "sa.split.n180"), (s30, o30, s100, s180) => s30 == 1 and o30 == 1 and s100 < 1 and s180 < 1)

== Experiment B. Structuring the log with a provenance graph <sec-graph>
The provenance graph improves detection when teams do not share records.
At zero overlap, all #n("sb.zero.fleets") fleets are identical to those used in the corresponding condition of Experiment A.
The graph-assisted monitor detects the split attack in #n("sb.split.o0") runs, compared with #n("sa.split.n100") without the graph.
#claim("the graph helps on the overlap-0 fleets", ("sb.split.o0", "sa.split.n100", "sb.same.fleets", "sb.zero.fleets"), (g, a, s, z) => g > a and s == z)
Each team forms a separate chain, allowing the monitor to isolate the chain containing both the private checkpoint and an enabled delivery.

As overlap increases, unrelated teams merge into the colluders' chain.
That chain grows from #n("sb.chain.o0") agents with no overlap to #n("sb.chain.o1") agents at overlap 1 and #n("sb.chain.o2") at overlap 2 (@fig-graph).
Detection falls from #n("sb.split.o05") at overlap 0.5 to #n("sb.split.o1") at overlap 1, #n("sb.split.o15") at overlap 1.5, and #n("sb.split.o2") at overlap 2.

Detection is closely associated with chain size.
The monitor detects attacks in #n("sb.small.caught") runs where the colluders' chain contains at most #n("sb.small.limit") agents, approximately a tenth of the fleet.
It detects only #n("sb.large.caught") when the chain is larger.
#claim("small chains are caught more often than large ones", ("sb.small.caught", "sb.large.caught"), (s, l) => s > l)

At overlap 4, nearly the entire fleet belongs to one chain.
The monitor returns to text search, which accounts for #pct("sb.calls.search.o4") of its calls compared with #pct("sb.calls.search.o0") at zero overlap (@fig-tools).
Detection remains low at #n("sb.split.o4").
Once the graph stops separating teams, the monitor faces the same search problem as in Experiment A, with a longer log because of the shared reads.

The retrieval results follow the same pattern.
None of the #n("sb.misses") missed attacks had all four required pieces of evidence retrieved, while all #n("sb.catches") detected attacks did (@tab-graph).
#claim("no missed graph run had retrieved all four steps", ("sb.misses.steps",), m => m == 0)
#claim("every caught graph run had retrieved all four steps", ("sb.catches.steps", "sb.catches"), (a, b) => a == b)
There are no false alarms on honest fleets (#n("sb.honest")), and their highest suspicion score is #n("sb.honest.max").
#claim("the graph monitor never flags an honest fleet", ("sb.honest",), h => h == 0)

The busy-record cutoff does not prevent this merging.
Each shared index is read by only two teams, keeping it below the cutoff.
Many small connections can therefore merge the chains even though no individual record is widely shared.

#figure(
  data-figure("sb-figure", width: 50%),
  caption: [*Shared-record overlap merges teams into larger chains and reduces detection.*
  Each square represents an attack fleet and shows the number of agents in the chain containing the three colluders.
  Solid squares indicate detection in every run, light squares indicate detection in some runs, and hollow squares indicate no detections.
  Shading marks chains containing at most a tenth of the fleet.
  No honest fleet is flagged (#n("sb.honest")).],
) <fig-graph>
#claim("the graph helps until overlap merges the fleet into one chain", ("sb.split.o0", "sb.split.o2", "sb.small.caught", "sb.large.caught"), (o0, o2, small, large) => o0 > o2 and small > large)

== Experiment C. Following the data <sec-flow>
Flow-graph monitoring detects every split attack in the tested conditions.
On the same #n("sc.curve.fleets") fleets used in Experiment B, it detects the attack in #n("sc.split.curve") judgments, compared with #n("sc.b.split") runs for the provenance-graph baseline (@fig-flow).
#claim("the flow graph beats B on B's own fleets", ("sc.split.curve", "sc.b.split", "sc.same.fleets", "sc.curve.fleets"), (c, b, s, z) => c > b and s == z)

Detection remains complete beyond Experiment B's tested range.
The method detects #n("sc.split.o8") attacks at overlap 8 and #n("sc.split.o16") at overlap 16.
It also detects #n("sc.split.n400") attacks in fleets of #n("sc.agents.n400") agents and #n("sc.split.n1600") in fleets of #n("sc.agents.n1600") agents.
No honest fleet is flagged (#n("sc.honest")).
#claim("the flow graph never flags an honest fleet", ("sc.honest",), h => h == 0)

In all #n("sc.judge.colluders") attack judgments, the group receiving the monitor's highest score consists of exactly the three colluders.
#claim("the monitor's top group is always the colluders", ("sc.judge.colluders",), c => c == 1)
Attack fleets receive scores of at least #n("sc.judge.attack.min"), while honest fleets receive scores of at most #n("sc.judge.honest.max") (@fig-scores).
#claim("attack and honest monitor scores don't overlap", ("sc.judge.attack.min", "sc.judge.honest.max"), (a, h) => a > h)
The two monitoring passes agree on all #n("sc.agree") fleets (@tab-flow).
#claim("the two passes always agree", ("sc.agree",), a => a == 1)

The monitor reads approximately #n("sc.judge.chars") characters per group, compared with #n("sc.log.chars") characters for the full log of a 100-team fleet.
Labeling costs #n("sc.usd.base") per 100-team fleet and #n("sc.usd.largest") for a fleet of #n("sc.agents.n1600") agents.

The flow graph and the monitor make distinct contributions.
In all #n("sc.graph.exact") attack fleets, the group with the highest flow score is exactly the three colluders.
#claim("the top flow group is always the colluders", ("sc.graph.exact",), c => c == 1)
Each attack fleet's highest flow score also exceeds that of its matched honest twin (#n("sc.graph.twin")).
#claim("every attack fleet's top flow score beats its twin's", ("sc.graph.twin",), t => t == 1)

However, flow scores overlap across different fleets.
The lowest top score among attack fleets is #n("sc.graph.attack.min"), while the highest among honest fleets is #n("sc.graph.honest.max"), from a fleet of #n("sc.graph.honest.max.agents") agents.
#claim("the flow scores alone don't separate attack from honest fleets", ("sc.graph.attack.min", "sc.graph.honest.max"), (a, h) => float(a) < float(h))
A single flow-score threshold therefore cannot perfectly separate attack and honest fleets in these experiments.
The monitor achieves that separation by reviewing the selected groups' actions against the policy.
@app-results describes the other groups it reviews.

#figure(
  data-figure("sc-figure", width: 100%),
  caption: [*Flow-graph monitoring detects every split attack in the tested conditions.*
  Detection is shown for the monitor without a graph (@fig-scaling), the provenance-graph baseline, and the flow graph paired with Step 1's joint monitor.
  Experiment C includes #n("sc.judgments") judgments across #n("sc.fleets") fleets, each monitored #n("sc.passes") times.
  Hatching marks conditions in which a method was not evaluated.],
) <fig-flow>
#claim("the flow graph catches every split attack, even where the provenance graph fails", ("sc.split", "sc.b.split"), (c, b) => c == 1 and b < 1)

= Discussion and Limitations
#todo[what the result does and does not establish]

The flow graph follows data through records, not through an agent's own context.
If one agent writes private data to a file, and a second agent reads that file and then emails what it read, the flow graph misses it.
The read writes nothing, so Jev gives it a low carrier probability and the data stops there; and the sink question asks about deliveries the synchronization service carries out, so a direct email may not count as one.
Two changes would cover this case: let a read whose result shows private data carry it into the agent's next action, and ask the sink question about any action that sends data outside the organization.
The shared reads that merge the provenance graph's chains show other teams' record names, not private data, so the first change should not let overlap merge the teams again.
Both changes alter the method after the results, so they would need a rerun on every fleet.

= Conclusion
Detecting a split attack requires finding which agents to review together.
In our controlled scenario, searching the raw log becomes unreliable as the fleet grows, while provenance-based grouping breaks down as shared records merge unrelated teams into large chains.

Our flow graph uses a decision model to label tool calls, links calls through their record references, and simulates possible data flows to identify candidate groups.
With the same monitor and decision threshold, it detects the split attack in #n("sc.split") judgments with no false alarms (#n("sc.honest")), in fleets of up to #n("sc.agents.n1600") agents.
The graph narrows the monitor's task from searching the full fleet to reviewing a few groups of agents.

#unnumbered[Code and Data]
The code, experiment logs, and paper build are available in the #link("https://github.com/tms7331/apart-research-sprint-swarmgraph")[project repository].
The `logs/` directory contains Step 1's episodes and monitor readings.
It also contains the fleets and complete monitor runs for Experiments A and B, including tool calls and results, and the selected groups and judgments for Experiment C.

Fleet generation is deterministic, so the fleets can be reproduced from the code.
The committed logs include Jev labels for every group reviewed by the monitor.
The full Jev cache is not included, so relabeling a fleet requires new Jev calls.

The paper's build system is preexisting work, ported from our earlier #link("https://github.com/carver/apart-research-collusion-sprint-2026")[AI Collusion Research Sprint project].
It generates the paper's numbers, tables, and figures from the logs and compiles the document.
The ported files are listed in `paper/README.md`.

Thomas Redfern participated in that earlier project.
The experiment code, data, and code that incorporates those results into the paper were developed for this sprint.

#unnumbered[LLM Usage Statement]
We decided on the experiments to run and the direction of the code, but directed Claude to write the code and help analyze the results of the experiments.
Code was developed with Claude Opus 5.5 and GPT-6-Astra.
For our decision model graph, the initial idea was to use the model to score edges.
This didn't scale well, and Claude helped explore variations that scaled better.

LLMs appear in the experiments in two roles: #n("tb.model"), through the Codex CLI, is every monitor, and Jev (#n("pr.jev.model")), a decision model, labels the tool calls in Experiment C.
No model plays the agents.

Initial drafts of this report's text, appendices included, were generated with AI.
The appendices are still almost fully AI generated, the core paper content was revised extensively by hand.

To keep errors out, every number, table and figure in the paper is filled in from the logs by the paper's build, not typed by a person or a model, the build checks the sentences whose wording depends on the data against those numbers, and every prompt in @sec-prompts is checked against the hash the run recorded.
We cite only sources that one of us, or an agent we directed, read in full.
We reviewed the code, results and text, and take responsibility for all of it.
= Limitations and Dual-Use / Ethical Considerations <app-limitations>
*Experimental scope.*
The experiments use one scripted exfiltration workflow, one attack, and two kinds of honest team.
Agents follow fixed actions, the data consists of short placeholders rather than real model weights, and the partner destination is a record rather than an external system.
The results do not establish performance with live agents, other attacks, authorized exports of private data, or attackers who adapt to the defense.
Experiment C evaluates only split attacks and honest controls.
We have not evaluated a complete system combining the flow graph with individual monitoring across a fleet.

Each condition has only #n("sb.layouts") layouts.
Repeated monitoring passes measure variation in judgments rather than additional attacks, so the reported rates are counts over a small set of fleets without confidence intervals.
Some evaluation fleets were also used during development (@app-development), and all fleets come from the same generator.

*Known failure cases.*
The graph can miss data passed through an agent's context.
For example, after one agent writes private data to a file, another might read it and email its contents.
A plain read receives a low carrier probability, and the sink question focuses on scheduled partner deliveries, so this path may not be detected.
The linker also depends on recognizable record names and can miss transfers through copied text or unfamiliar identifiers.

Forward-only links create another gap.
If an agent enables delivery before another updates the package to point to private data, the service can still export that data after both agents finish.
The graph would miss the connection because the relevant write occurs after the delivery action.

*Evaluation conditions.*
The method uses only the operator's public log, with colluder identities used afterwards to score the results.
Several features nevertheless make this setting easier than real logs.
Private data is explicitly marked, record names follow a fixed pattern, and team tags identify the policy paragraphs supplied to each group.
The added overlap consists of shared index reads that do not transfer underlying data.
We have not tested honest workflows in which one team's outputs become another team's inputs, which could produce larger candidate groups.

Experiment B was not evaluated on the larger fleets or at overlap above 4, so its behavior there is inferred rather than measured.
Experiment A was not evaluated with overlap.
All experiments use one monitor model, #n("tb.model"), at one reasoning effort, and Experiment A uses one exploration prompt.
Different models or prompts could change where the baselines break down.

*Ethical considerations.*
The split-attack pattern is already public @kitaoka2026, but documenting monitoring gaps could help attackers evade a defense.
Operator logs should be treated as sensitive because they can contain the data agents access.
A flag should trigger human review rather than automatic action against agents or their users.
The experiments used synthetic data and scripted agents without exporting real private data to an outside system.

= Further related work <app-related>
AScope @cai2026 traces agents, processes, files, and network connections, then uses an LLM to review risky chains against the session's intent within one orchestrated system.
Follow the Text @juhl2026 uses a shared registry and write-before-read timing to identify communication in agent transcripts, without evaluating the harmful effects of combined actions.
Hossain and Haldar @hossain2026 link state-key writes to later reads within one agent's trajectory and trace paths from injected inputs to sensitive sinks.
Our setting instead requires finding the relevant team among independent agents performing similar work.

= The attack in the log <app-log>
#figure(
  data-table("lx-log"),
  caption: [*The attack appears as three ordinary-looking updates.*
  Each colluder's update is shown alongside the two preceding calls by other agents in a #n("lx.agents")-agent fleet.
  Agent IDs and long values are shortened.
  Similar updates also appear in honest teams' logs.],
) <tab-log>

= Flow-graph implementation details <app-flow>
These notes supplement the method in @sec-flow-method.
The exact labeling questions are provided in @sec-prompts.

== Implementation notes
The source label includes references to records that the policy explicitly marks as private.
The carrier label asks whether a call writes data or a reference onward, regardless of whether that data is currently known to be private.
The sink label concerns the delivery configuration left by an action, since the delivery itself is outside the agents' visible log.
Jev responses are cached by the full request, and missing or refused answers would receive a probability of 0.5.

The linker recognizes record names by their form, consisting of a word, six hexadecimal digits, and another word separated by slashes.
It applies no special cases for particular fields or records and retains links regardless of how many agents mention a record.
Each simulation round samples one source answer and one carrier answer per call, regardless of its number of incoming links.
Random draws are derived from the call ID and question, so rerunning the simulation produces the same rounds.

For each call and round, the simulation records whether it holds private data and whether it received that data by carrying it rather than being a source.
This allows paths to be reconstructed after scoring without storing them during the simulation.
For each highly ranked call, backtracking starts from the rounds in which it was hit and follows parents that held data.
It continues through carriers and stops at sources.
Calls appearing in at least #n("sc.keep") of those rounds determine the candidate group's agents.
Groups can overlap, and many agents need not appear in any group.
Flow scores range from 0 to 1 and select groups for review, while the monitor's suspicion scores range from 0 to 100 and determine whether the fleet is flagged.

== A worked example
@fig-example shows an attacking team A and an honest team S, each with three agents.
Team S's staging agent also reads a shared index that names team A's package entry.
The probabilities are illustrative values chosen close to Jev's outputs on real fleets.
The results come from the actual simulation, using #n("fx.worlds") rounds rather than #n("sc.worlds") to make the example's estimates more stable.

The shared read would merge the teams in the provenance graph, but its low carrier probability passes little data onward in the flow graph.
A read can also have a high hit rate while receiving a low flow score because it does not enable an export (@tab-scores).
Team S's delivery receives some flow through its own staging step, whose moderate source probability reflects a reference to a bundle with unseen contents.
Team A's delivery scores #n("fx.score.a"), compared with #n("fx.score.s") for team S, and its selected group is the #n("fx.group.a").

#figure(
  data-figure("fx-figure", width: 100%),
  caption: [*A worked example of data flow across agents.*
  The left panel shows tool-call nodes with illustrative source, carrier, and sink probabilities, linked by record references.
  The right panel shows the fraction of #n("fx.worlds") rounds in which data passes along each link.
  These link percentages are for illustration only.
  The method scores calls, and each delivery is labeled with its flow score.],
) <fig-example>

#figure(
  data-table("fx-scores"),
  caption: [*Scores after #n("fx.worlds") simulation rounds.*
  Each flow score is the hit rate multiplied by the sink probability.
  Staging and index-read calls can be hit without enabling a delivery.],
) <tab-scores>

== Method development <app-development>
We developed the method using layout-0 fleets from Experiment B, including attacks and their honest twins.
Jev's questions were worded using the overlap-4 condition.
When we extended the evaluation to overlap 8, the busy-record cutoff inherited from Experiment B removed a link needed to detect the attack.
We removed that cutoff and froze the labeling questions, linking rules, simulation, and monitor setup.
Layouts 1 to 3 were then evaluated as held-out fleets.
The reported results include the development fleets, including the overlap-4 condition used for question wording and the overlap-8 condition that prompted the cutoff change.
All layouts and conditions come from the same fleet generator.

== Provenance baseline implementation <app-graph>
Experiment B retains FragBench's event graph and connected chains but omits links based on argument similarity.
It replaces down-weighting of common resources with a fixed busy-record cutoff.
An LLM monitor reviews the discovered chains in place of FragBench's trained per-event detector.
The comparison therefore evaluates this baseline implementation rather than the full FragBench defense.

= Supplementary results <app-results>
The detailed results for Step 1 and Experiments A, B, and C are provided in @tab-tb, @tab-scaling, @tab-graph, and @tab-flow.
@fig-tools shows how the provenance-graph monitor shifts toward text search as overlap increases.

#figure(
  data-figure("sb-tools", width: 100%),
  caption: [*The monitor shifts from graph tools to text search as overlap increases.*
  Tool calls are grouped by kind for fleets of #n("sb.agents") agents, with detected split attacks shown above each bar.
  The figure covers #n("sb.explorations") runs, with each fleet monitored #n("sb.passes") times.],
) <fig-tools>
#claim("as overlap grows, the monitor abandons the graph for text search", ("sb.calls.graph.o0", "sb.calls.graph.o4", "sb.calls.search.o0", "sb.calls.search.o4"), (g0, g4, s0, s4) => g4 < g0 and s4 > s0)

The other groups reviewed in Experiment C contain #n("sc.others.agents") agents, an honest team's staging and sync agents (#n("sc.others.pair")).
The simulation reaches their delivery through the staging step's moderate source probability.
These groups show a package pointing to a bundle and an enabled delivery, but do not reveal the bundle's contents, so the monitor scores them below the threshold.
The colluders' group also includes the backup agent, whose copy exposes the private checkpoint, and receives a higher score (@fig-scores).
#claim("every other group is one honest team's staging and sync agents", ("sc.others.pair",), p => p == 1)

The monitor labels every top group as a precursor rather than a completed violation (#n("sc.judge.precursor")).
The actual delivery occurs in the service's records and is not visible to the monitor.
#claim("every top group is assessed as a precursor", ("sc.judge.precursor",), p => p == 1)

#figure(
  data-figure("sc-scores", width: 100%),
  caption: [*Monitor scores separate attack fleets from honest fleets.*
  Scores are shown for each judgment of an attack fleet and its matched honest twin under each condition.
  The dashed line marks the flagging threshold.],
) <fig-scores>
#claim("the monitor's scores for attacks and honest fleets never overlap", ("sc.judge.attack.min", "sc.judge.honest.max", "sc.threshold"), (a, h, t) => a >= t and h < t)

#figure(
  data-table("tb-table"),
  caption: [Step 1 median scores under individual and joint review, including each agent's median score.
  The individual-review team score is that of its highest-scoring member.],
) <tab-tb>

#figure(
  data-table("sa-table"),
  caption: [Experiment A detection and false alarms by fleet size, with median tool calls and input tokens per run.
  Counts combine four layouts and #n("sa.passes") monitoring passes.],
) <tab-scaling>

#figure(
  data-table("sb-table"),
  caption: [Experiment B results by overlap, including colluder-chain sizes, detection, false alarms, graph-tool use, and median calls and input tokens.
  Counts combine four layouts and #n("sb.passes") monitoring passes.],
) <tab-graph>

#figure(
  data-table("sc-table"),
  caption: [Experiment C results by fleet condition, with detection counts from each method's own runs.
  The table also reports false alarms across four layouts and #n("sc.passes") passes, monitor score ranges, and labeling cost per fleet.],
) <tab-flow>

= Prompts and questions <sec-prompts>
The texts below are extracted from the experimental code and checked against hashes recorded in the run logs.
Jev's questions are also checked against the digest in the run protocol.
Braces indicate values filled in for each fleet.

== The scenario
The policy below is from Step 1's layout-0 episodes.
A fleet's policy contains one such paragraph per team.
#data-text("pr.policy")
The service descriptions are shared by all teams.
#data-text("pr.services")
The split team's tasks specify each agent's read and write permissions.
#data-text("pr.tasks")

== The monitor for Step 1 and Experiment C
These instructions are followed by the word EVIDENCE and JSON containing the policy, agent tasks, tool calls, results, and messages.
Run IDs and timestamps are excluded.
#data-text("pr.monitor")

== The search monitor for Experiment A
The instructions are followed by the policy, service descriptions, previous calls and results, and remaining call budget.
#data-text("pr.explorer")

== The graph tools for Experiment B
Experiment B adds the following tool instructions to Experiment A's prompt.
#data-text("pr.graph")

== Jev's questions for Experiment C
Jev returns a probability of yes for each question.
#data-text("pr.jev")

#unnumbered[LLM Usage Statement]
We decided on the experiments to run and the direction of the code, but directed Claude to write the code and help analyze the results of the experiments.
Code was developed with Claude Opus 5.5 and GPT-6-Astra.
For our decision model graph, the initial idea was to use the model to score edges.
This didn't scale well, and Claude helped explore variations that scaled better.

LLMs appear in the experiments in two roles: #n("tb.model"), through the Codex CLI, is every monitor, and Jev (#n("pr.jev.model")), a decision model, labels the tool calls in Experiment C.
No model plays the agents.

Initial drafts of this report's text, appendices included, were generated with AI.
The appendices are still almost fully AI generated, the core paper content was revised extensively by hand.

To keep errors out, every number, table and figure in the paper is filled in from the logs by the paper's build, not typed by a person or a model, the build checks the sentences whose wording depends on the data against those numbers, and every prompt in @sec-prompts is checked against the hash the run recorded.
We cite only sources that one of us, or an agent we directed, read in full.
We reviewed the code, results and text, and take responsibility for all of it.
