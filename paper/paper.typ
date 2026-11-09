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

@app-flow provides further details, a worked example, an application to a full fleet, and an account of how we developed the method.

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
This fixed cutoff replaces FragBench's approach of down-weighting common resources.

We use union-find to group connected events into chains.
Graph construction depends entirely on the log and requires no model calls.
Without overlap, each team forms its own chain.
With overlap, a shared-index read can connect two teams' chains, and a series of such connections can merge multiple teams into one chain (@app-graph).

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
== Reproducing the fragmentation result <sec-step1>
#todo[the reproduction of the fragmentation result, from the full run]
Reading each agent individually, the monitor flags #n("tb.solo.flagged") solo attacks and #n("tb.split.flagged") split attacks; reading each team together, it flags #n("tb.split.joint.flagged") split attacks (@fig-tb).
On honest teams, reading individually gives #n("tb.honest.flagged") false alarms and reading together #n("tb.honest.joint.flagged") (@tab-tb).

#figure(
  data-figure("tb-figure", width: 100%),
  caption: [*Splitting an attack hides it from a monitor that reads each agent individually.* Each row is one team (run #n("tb.run")); its arrow runs from its score read individually (the median for its highest-scoring member) to its score read together (the median for the whole team). Teams right of the dashed threshold are flagged. The honest teams take the same three steps as the attack but ship the shareable file; the incomplete attacks shown are missing their backup step, so nothing private leaves. Solo teams, honest maintenance teams and the other incomplete attacks are in @tab-tb.],
) <fig-tb>
#claim("splitting an attack hides it from a monitor that reads each agent individually", ("tb.split.flagged", "tb.solo.flagged"), (split, solo) => split < solo)


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

#figure(
  data-figure("sb-figure", width: 50%),
  caption: [*The graph helps until overlap merges the fleet into one chain.* Agents in the chain that holds the three colluders, one square per attack fleet: solid where the monitor caught the attack in every run, light where it caught it in some, hollow where it never did; shaded, chains of at most a tenth of the fleet. No honest fleet is flagged (#n("sb.honest")).],
) <fig-graph>
#claim("as overlap grows, the monitor abandons the graph for text search", ("sb.calls.graph.o0", "sb.calls.graph.o4", "sb.calls.search.o0", "sb.calls.search.o4"), (g0, g4, s0, s4) => g4 < g0 and s4 > s0)
#claim("the graph helps until overlap merges the fleet into one chain", ("sb.split.o0", "sb.split.o2", "sb.small.caught", "sb.large.caught"), (o0, o2, small, large) => o0 > o2 and small > large)


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

#claim("the judge's scores for attacks and honest fleets never overlap", ("sc.judge.attack.min", "sc.judge.honest.max", "sc.threshold"), (a, h, t) => a >= t and h < t)


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

= Limitations and Dual-Use / Ethical Considerations <app-limitations>
*What the result establishes.*
In one scripted exfiltration scenario, with one attack and two kinds of honest team, a flow graph built from cheap per-call labels and mechanical links finds the attacking team in fleets of up to #n("sc.agents.n1600") agents, with tool-call overlap that breaks a provenance graph, and the monitor reading that team flags every attack fleet and no honest one.
It also establishes that, in this scenario, a tool-using monitor over the raw log and a FragBench-style provenance graph each have a breaking point, and that their misses come from finding the evidence, not from judging it.

*What it does not establish.*
It does not show that the method works on live agents, on other attacks such as sabotage, on honest work that legitimately exports private data, on logs whose records aren't named in a regular pattern, or against attackers who know how the monitor works.
It does not show that the per-agent monitor and the flow graph together cover every attack: the flow graph leaves single agents to the per-agent monitor, and we tested that monitor at fleet scale only in Experiment A.
Its rates are counts over a few distinct fleets per condition, and the method was developed on some of the fleets it is evaluated on (@app-flow).
The agents' records hold short placeholder data rather than real model weights, and the partner is a record, not an outside system.

*What the flow graph does not catch.*
The flow graph follows data through records, not through an agent's own context.
If one agent writes private data to a file, and a second agent reads that file and then emails what it read, the flow graph misses it.
The read writes nothing, so Jev gives it a low carrier probability and the data stops there; and the sink question asks about deliveries the synchronization service carries out, so a direct email may not count as one.
Two changes would cover this case: let a read whose result shows private data carry it into the agent's next action, and ask the sink question about any action that sends data outside the organization.
The shared reads that merge the provenance graph's chains show other teams' record names, not private data, so the first change should not let overlap merge the teams again.
Both changes alter the method after the results, so they would need a rerun on every fleet.
A solo attack is left to the per-agent monitor by design, and data passed without a record name, such as copied text, needs links that a model judges ("did this call use that one's output?"), which our prototype tried and found less robust at scale.
Links point forward in time, which works here because our agents act in role order: backup, then staging, then sync.
The service reads the records after the agents have finished, so the order doesn't change what it delivers, but if the sync agent switched the delivery on before the staging agent pointed the package at the bundle, no link would join the two and the flow graph would miss the attack; an attacker can choose the order.
Linking a write to earlier calls that name its record as well would cover this, at the cost of the single pass in time order, since the graph could then have cycles.

*How fair the comparison is.*
Nothing in the method reads the ground truth: Jev, the links, the simulation and the monitor see only the operator's public log, and the colluders' IDs are used only afterwards, to score our results.
Five things still make our setting easier than real logs.
First, we worded Jev's questions on a prototype run of Experiment B's overlap-4 fleets in one layout, and removed a cutoff for busy records after seeing it fail at overlap 8; both conditions are among the results, and held-out layouts and sizes agree, but every fleet comes from the same generator.
Second, the private data announces itself: the record's contents and its export flag are visible in the log, and the policy names the private file, which makes Jev's source question easy.
Third, the linker finds record names with a pattern that matches this scenario's names exactly; real logs would need it to recognize file paths, URLs and table names.
Fourth, the monitor's policy is cut to the paragraphs for the group's teams using the scenario's team tags; the policy is public, so this is fair, but it relies on the policy being organized that way.
Fifth, the overlap we add consists of shared reads of listings, which pass no data: the kind of sharing that merges the provenance graph's chains and that the flow graph's carrier label is built to discount.
Honest teams whose work really depends on each other's records, one team writing what another later uses, would add real cross-team flows, and so larger honest groups for the monitor to clear; we haven't tested them.

*Other limitations.*
Every fleet comes from one scripted scenario: one kind of attack, two kinds of honest team, and agents whose actions are fixed in advance rather than live models that could fumble, improvise or give themselves away.
A third kind of honest team, private data that is authorized for export and goes to a partner legitimately, would test that the method follows the policy and not just the private data; we haven't built it.
Each condition has only #n("sb.layouts") layouts, and repeated passes measure the monitor's noise, not new attacks, so our rates are counts out of a few distinct fleets per condition, with no intervals.
We did not run Experiment B on the scaling arm, so past overlap 4 its failure is inferred from the merged chains, not measured; nor did we run Experiment A on fleets with overlap.
The attackers know nothing about the monitor; an attacker who did could route data through an agent's context, through records whose names the linker doesn't match, or through a delivery the sink question doesn't recognize.
Experiment A uses one prompt, so its breaking point is that prompt's; clearer instructions could move it.
Every monitor is one model, #n("tb.model"), at one reasoning effort; a weaker trusted monitor would make the monitor's job harder, though in Experiment C it reads far less than a whole-log monitor would.

*Dual use.*
The attack pattern itself, a harmful objective split into steps that are each allowed, is already public @kitaoka2026, and our version is a fixed script of three pointer changes, not a capability an attacker lacks.
The more sensitive part is the description of what the monitor can't see: an attacker who read this paper would know to move data through an agent's own context, through channels without record names, or through a delivery that doesn't look like one.
We think publishing it helps defenders more than attackers, since these gaps follow from any record-based provenance method and the fixes are stated alongside them.
The method itself is a defense, and it needs the operator's logs of every agent's tool calls; a deployment should treat those logs as sensitive, since they hold whatever data the agents touched.
A monitor that flags groups of agents could also be wrong about honest ones; in our fleets the monitor scored honest groups below the threshold, but in deployment a flag should start a review, not an action against the agents.
No real data, systems or people were involved, and no agent was given a harmful instruction: the agents' actions are fixed in code.

= Further related work <app-related>
AScope @cai2026 builds a provenance graph over agents, processes, files and network connections and has an LLM check the highest-risk chains against the session's intent; it already links one agent's write to another's read through a shared file, but every scenario is one orchestrated system attacked from outside, with no population of independent agents among which to find a team.
Follow the Text @juhl2026 links agents through a shared registry in Hugging Face–style transcripts, checking each link against write-before-read timing, and detects communication rather than harmful composition.
Hossain and Haldar @hossain2026 join a state-key write to a later read of that key in one agent's trajectory and measure paths from an injected input to a sensitive sink, a single-agent version of our write-to-reference links.
Our carrier label plays the role that tag attenuation plays in provenance-based intrusion detection, where benign processes pass less taint on so that taint doesn't spread through everything.
Estimating reachability by sampling each uncertain step and averaging over the samples is the standard Monte Carlo estimator for reachability in uncertain graphs.

= The attack in the log <app-log>
#figure(
  data-table("lx-log"),
  caption: [*The attack is three ordinary-looking lines in a log of thousands.* Each colluder's change (step) in one #n("lx.agents")-agent fleet, with the two calls by other agents just before it; agent IDs and long values shortened. Each colluder's change has honest look-alikes elsewhere in the log.],
) <tab-log>

= The flow graph in detail <app-flow>
This appendix works through each step of the method of @sec-flow-method in more detail, then through a small example, then through one real fleet, and says how we arrived at the method.

== Nodes and labels
*Nodes are tool calls, and each knows its agent.* The nodes are individual tool calls, one per call in the log, not tools and not records.
A record never becomes a node; it only justifies a link between two calls.
If one agent writes a file and another later reads it, the graph has two nodes, the write call and the read call, and one link from the write to the read.
If one write is followed by reads from fifty agents, the graph has fifty-one nodes and fifty links, one from the write to each read, and no links among the reads, since none of them wrote anything.
Every call in the operator's log carries the ID of the agent that made it, so each node knows its agent, and comparing two nodes' agent IDs tells us whether data crossed from one agent to another.
A platform that runs agents always records which agent made which call; what the defender does not know is which agents work together, and that is what the graph has to find.

*What Jev's three numbers mean.* They are not categories: they are three separate probabilities between 0 and 1, and an action can be high on more than one.
The backup agent's copy of the checkpoint, for instance, is likely both a source and a carrier.
Source asks whether the action reads, copies or points to data the policy marks private.
Carrier asks whether, if data came into the action, the action would pass it on into another record by writing onward; it does not ask whether the action holds private data now.
A plain read of private data is therefore a likely source but not a carrier, since it writes nothing.
Sink asks whether the action sends data outside the organization; writing to an internal record does not count.
No data moves in the agents' own view, so the sink question asks about the configuration an action leaves behind: whether, after it, an enabled delivery to an outside destination will run.

*How Jev is asked.* Jev (#n("pr.jev.model"), on OpenRouter) gets one request per tool call, holding only what the monitor would see of that call: the services text, the policy paragraphs for the teams the call, its result or its agent's task mention, the agent's task, the call and its result (@sec-prompts shows one request in full).
It never sees run IDs, timestamps, the service's records or the ground truth, and it sees one call at a time, never a transcript.
Each question has instructions and a one-line meaning for yes and for no, written in terms of the policy and the services, not of our record names.
We worded the questions on one development fleet and then froze them for every other fleet (see how we arrived at the method, below).
Over all #n("sc.fleets") fleets, Jev answered #n("sc.jev.requests") requests; #n("sc.jev.refused") answers came back refused or missing (each would have counted as 0.5), and #n("sc.jev.long") requests were long enough for Jev's slower long-context mode.
Every answer is cached by its full request, so our reruns made no paid calls and gave the same labels; the cache isn't in the repository.

== Links and simulation
*Which records make a link.* A link needs a write first.
An action that writes a record links to every later action that names it, whether that later action reads it, changes it, or only mentions it in its result.
A read followed by a write of the same record gives no link, because the read wrote nothing, and two reads of the same record give no link either.
Links carry no numbers, and every link points from an earlier call to a later one.
The links say only where data could flow; the nodes' numbers decide, round by round, whether it does.
Record names are found by their shape in this scenario (a word, six hexadecimal digits and a word, separated by slashes), with no special cases for particular fields or records.
In the attack, the backup agent's copy writes the bundle and the staging agent's change names it; the staging agent's change writes the package entry, and the sync agent's read of the schedule returns a record that names it; so the three colluders' calls are linked in a chain, as are every honest team's.
There is no cutoff for busy records: every link is kept, and the carrier labels decide how much passes along it.

*One round, in detail.* Within a round, nothing is a probability: every call gets plain yes-or-no answers.
Each call draws once for source and once for carrier, so a call with three incoming links still has a single carrier answer for the round.
A call holds private data if it is a source in the round, or if any of its parents, the calls with links into it, holds data and the call is a carrier in the round; one parent holding data is enough.
Only the direct parents are checked: their answers already reflect everything earlier in the log, and going through the log in time order means every parent is settled before its children are reached.
Whether a call is hit is then a direct calculation, with no further draw: it is hit if some parent that holds data in this round belongs to a different agent.
A parent from another agent that holds nothing in the round does not count.
The one extra case is a parent by the same agent, which counts only when that parent was itself hit and is a carrier, so that an agent can hand data it received from another agent on to its own next call.
Across rounds the yes-or-no answers become rates: a call hit in seven rounds out of ten has a hit rate of 0.7.
The random numbers come from a hash of each call's ID and the question, so a rerun draws exactly the same rounds.

== Scores, candidate groups, and coverage
*Hit rate and flow score.* The hit rate is how often private data reached the call from another agent.
The flow score multiplies it by the call's sink probability, so, under Jev's labels, it estimates how often the call sends private data that came from another agent out of the organization.
The difference matters: a call that reads a shared index can be reached by private data as often as the attack's delivery, but its sink probability is near zero, so its flow score is near zero.
The flow score, a number between 0 and 1 from the simulation, is distinct from the monitor's score, a suspicion score from 0 to 100; the monitor never sees the flow scores, and its scores are the ones in @fig-scores.

*What the rounds keep, and how groups are rebuilt.* The simulation does not store paths.
For every call and every round it keeps two yes-or-no flags: whether the call holds private data, and whether it got that data by carrying it rather than by being a source.
That table, one row per call and one column per round, is enough to rebuild any path afterwards, and paths are rebuilt only for the few top-scoring calls, only at the end.
For a top call, we take the rounds in which it was hit and, in each, trace backward: every parent that held data in that round is added, the trace continues from a parent that got its data by carrying it, and it stops at a parent that was a source.
Counting across those rounds, we keep the calls that appear in at least #n("sc.keep") of them, and look up each kept call's agent: that set of agents is the group.
The calls are ranked by flow score, a group whose agents match one already found is skipped, and the monitor reads the first #n("sc.groups") groups.

*Groups are candidates, not verdicts, and not a clustering.* The graph does not decide which agents are suspicious: it finds the few groups through which private data could plausibly travel, across agents, to an outside delivery.
Honest teams that ship data out appear among them too, which is why the monitor reads each group.
Nor is it a clustering of the fleet: most agents are in no group, only a few groups are built, and two groups can share an agent.
Each group the monitor reads holds those agents' full transcripts, every task, tool call, result and message, with the policy paragraphs for their teams.
The monitor's view here is Step 1's group view, the same instructions and the same kind of evidence, restricted to the group's agents.

*Why only data that crosses agents counts.* If one agent reads private data and sends it out itself, its delivery is never hit, its flow score is 0, and the flow graph never sends it to the monitor.
That is by design: such a leak lies entirely in the agent's own transcript, which a monitor reading each agent individually catches, as in Step 1 (#n("tb.solo.flagged") solo attacks flagged).
The intended monitor runs both, the per-agent monitor for single agents and the flow graph with the monitor for groups; we tested the group half only, since Experiment C's fleets hold no solo attacks, and the per-agent half only on single teams, not at fleet scale.
The same simulation could cover single agents cheaply: it already records how often each call holds private data, crossing or not, so a solo score, that share times the sink probability, could send the top single agents to the monitor as groups of one.

== A small example
@fig-example shows the method on two teams of three, an attack team A and an honest team S that ships shareable data, whose staging agent also reads a shared index that lists team A's package entry.
Its probabilities are illustrative, chosen close to what Jev gave on the real fleets; the flow comes from the real simulation run on this graph, with #n("fx.worlds") rounds instead of #n("sc.worlds") so the example's numbers are steady.
The graph has a node for each of the seven calls and a link for each record that one call writes and a later call names, plus the same-agent link from S's read of the index to its next call.
@tab-round follows the first round.
The backup's copy draws a source answer of yes, so it holds private data (#n("fx.r0.a1.holds")); it is not hit (#n("fx.r0.a1.hit")), since nothing reached it from another agent.
The staging change draws no for source and yes for carrier, so it holds data too (#n("fx.r0.a2.holds")), and since the data came from the backup agent, a different agent, it is hit (#n("fx.r0.a2.hit")).
The delivery is hit too (#n("fx.r0.a3.hit")), because its parent, the staging change, holds data and belongs to another agent; being hit doesn't depend on the delivery's own carrier answer, and in this round it holds nothing onward (#n("fx.r0.a3.holds")).
Over all the rounds, team A's delivery scores #n("fx.score.a") and team S's #n("fx.score.s") (@tab-scores), and the group behind team A's delivery is the #n("fx.group.a").
Team S's delivery is reached mostly through its own staging step, whose moderate source probability stands for an agent that points at a bundle whose contents it can't see; the shared index passes almost nothing, because a plain read is rarely a carrier.
In the provenance graph, the same shared read would merge the two teams into one chain.

#figure(
  data-figure("fx-figure", width: 100%),
  caption: [*Following the data through a small example.* Left, the graph as built: each node is a call, with Jev's three probabilities (illustrative here), and each link is labelled with the record that makes it; links carry no numbers. Right, the flow found on it over #n("fx.worlds") rounds: the percentages on links are only for the picture (the share of rounds in which private data passes along the link), since the method scores nodes, not links; each delivery is labelled with its flow score.],
) <fig-example>

#grid(columns: (1fr, 1fr), gutter: 1.2em,
  [#figure(
    data-table("fx-round"),
    caption: [*One round of the small example.* Each answer is yes when the random number is below the probability; the sink probability is never drawn.],
  ) <tab-round>],
  [#figure(
    data-table("fx-scores"),
    caption: [*The small example after #n("fx.worlds") rounds.* Flow score = hit rate × P(sink): the staging change and the index read are hit, but aren't deliveries.],
  ) <tab-scores>],
)

== One real fleet, step by step
In one #n("sc.ex.agents")-agent fleet at overlap #n("sc.ex.overlap"), the one we developed the method on, Jev labelled #n("sc.ex.calls") tool calls and the linker made #n("sc.ex.links") links, about one per call.
The backup agent's copy into #raw(ledger.at("sc.ex.source.record").value) got a source probability of #n("sc.ex.source.source"), a carrier probability of #n("sc.ex.source.carrier") and a sink probability of #n("sc.ex.source.sink").
The staging agent's change of #raw(ledger.at("sc.ex.carrier.record").value) got #n("sc.ex.carrier.source"), #n("sc.ex.carrier.carrier") and #n("sc.ex.carrier.sink"), and the sync agent's change of #raw(ledger.at("sc.ex.sink.record").value) got #n("sc.ex.sink.source"), #n("sc.ex.sink.carrier") and #n("sc.ex.sink.sink").
Private data reached the sync agent's delivery from another agent at a hit rate of #n("sc.ex.hit"), for a flow score of #n("sc.ex.score"), against #n("sc.ex.next") for the next group; the top group was #n("sc.ex.who").
The monitor scored the colluders #n("sc.ex.judge.top") and the next two groups #n("sc.ex.judge.rest"), so the fleet was flagged.
At this overlap, over its #n("sb.layouts") layouts and #n("sb.passes") passes, the provenance-graph monitor caught the attack in #n("sb.split.o4") runs.

== How we arrived at this method <app-development>
We developed the method on the layout-0 fleets of Experiment B's curve, both the attack fleets and their honest twins, so that false alarms counted from the start.
We first built several ways to make the graph with Jev, including ones in which Jev scored each link or picked each call's parents, and several ways to analyse it with no model calls, including walks from risky calls, trees joining them, spreading scores and the simulation above.
Only the combination of node labels with the simulation put the three colluders on top, above every honest twin, at every overlap level of layout 0.
We then tried it on bigger fleets and more overlap, still in layout 0, where it failed at overlap 8: we had copied Experiment B's cutoff for busy records, and from overlap 8 the attacking team's own package entry is named by more agents than the cutoff allows, because of the shared-index reads, so the cutoff deleted the link from the staging change to the delivery.
We removed the cutoff, which needed no new labels, and froze the questions, the links, the simulation and the monitor's setup.
Layouts 1 to 3 of every condition were then run once, as held-out fleets.
The layout-0 fleets are among the results, as are the overlap-4 fleet we worded the questions on and the overlap-8 fleet that broke the cutoff.

= The provenance graph in detail <app-graph>
Within one team, the attack forms one chain on its own.
The backup and staging agents both name the bundle, and the staging and sync agents both name the package entry, so with no overlap each team, attacking or honest, is a chain of its own and the fleet has one chain per team.
With overlap, a team's staging agent also reads a shared index that lists another team's package entry; that read names the other team's record, so the two teams' chains join.
Union-find makes the joins transitive, so a few shared reads per team are enough to merge most of the fleet.
Compared with the full FragBench defense, we keep its event graph and chains, but drop its links between similar arguments, replace its down-weighting of busy records with the fixed cutoff, and put the LLM monitor in place of its trained per-event detector.

= Results in detail <app-results>
The tables behind the figures of @sec-results, one per experiment, and results the main text leaves out.

*Step 1.*
In every split team (#n("tb.split.sync.top")), the highest-scoring member read individually is the sync agent, which switches the delivery on; its median of #n("tb.split.sync") is about as high as that of an honest team's sync agent switching on a delivery of shareable data (#n("tb.honest.sync")), and both are below the threshold.
#claim("in every split team the sync agent scores highest, below the threshold like an honest sync agent", ("tb.split.sync.top", "tb.split.flagged", "tb.honest.flagged"), (top, split, honest) => top == 1 and split == 0 and honest == 0)
The backup agent, which copies the private checkpoint, scores #n("tb.split.backup"), since internal backups are allowed (@tab-tb).

*Experiment A.*
Seeing each attacking agent is not enough: #n("sa.misses.saw.all") of the misses had seen some event of every attacking agent, such as its task in a search result, without the step that gives it away.
At the largest fleet, a run reads a median of #n("sa.tokens.largest") thousand input tokens.

*Experiment B.*
As overlap grows, the monitor abandons the graph for text search (@fig-tools).

#figure(
  data-figure("sb-tools", width: 100%),
  caption: [*As overlap grows, the monitor abandons the graph for text search.* The monitor's tool calls by kind (graph tools list, search and read the graph's chains) at #n("sb.agents") agents, with the split attacks it caught above each bar (#n("sb.explorations") runs: each fleet monitored #n("sb.passes") times).],
) <fig-tools>
#claim("as overlap grows, the monitor abandons the graph for text search", ("sb.calls.graph.o0", "sb.calls.graph.o4", "sb.calls.search.o0", "sb.calls.search.o4"), (g0, g4, s0, s4) => g4 < g0 and s4 > s0)

*Experiment C.*
Every other group the monitor reads, in attack fleets and honest ones alike, has #n("sc.others.agents") agents: an honest team's staging and sync agents (#n("sc.others.pair")), whose delivery the simulation reaches through the staging step's moderate source probability, without the backup agent.
#claim("every other group is one honest team's staging and sync agents", ("sc.others.pair",), p => p == 1)
Such a group shows a package pointed at a bundle and a delivery switched on, but not what the bundle holds, so the monitor calls it a possible precursor and scores it below the threshold.
The colluders' group adds the backup agent, whose copy shows the private checkpoint going into that bundle, and the monitor scores it well above the threshold (@fig-scores).
The monitor assesses every top group as a precursor rather than a completed violation (#n("sc.judge.precursor")), since the delivery itself happens in the service's records, which no monitor sees.
#claim("every top group is assessed as a precursor", ("sc.judge.precursor",), p => p == 1)

#figure(
  data-figure("sc-scores", width: 100%),
  caption: [*The monitor's scores for attacks and honest fleets never overlap.* The monitor's score on each of the flow graph's judgments, attack fleet against its honest twin, under each condition; dashed, the flag threshold.],
) <fig-scores>
#claim("the monitor's scores for attacks and honest fleets never overlap", ("sc.judge.attack.min", "sc.judge.honest.max", "sc.threshold"), (a, h, t) => a >= t and h < t)

#figure(
  data-table("tb-table"),
  caption: [Median score per episode, read individually (the highest-scoring member) and read together, with each member's median.],
) <tab-tb>

#figure(
  data-table("sa-table"),
  caption: [Experiment A by fleet size: attacks caught and honest fleets falsely flagged (out of four layouts × two passes), with the median calls and input tokens per run.],
) <tab-scaling>

#figure(
  data-table("sb-table"),
  caption: [Experiment B by overlap: the colluders' chain in each layout, attacks caught and honest fleets falsely flagged (out of four layouts × #n("sb.passes") passes), the share of calls that used a graph tool, and the median calls and input tokens per run.],
) <tab-graph>

#figure(
  data-table("sc-table"),
  caption: [Experiment C by fleet: split attacks caught by B's graph monitor (its runs) and by the flow graph, honest fleets falsely flagged (out of four layouts × two passes), the range of the monitor's scores, and the Jev labelling cost of one fleet.],
) <tab-flow>

= Prompts and questions <sec-prompts>
Each text below is taken from the code that ran, and the paper's build checks it against the run's logs first: a prompt rebuilt from the code must hash to the one the run recorded, and Jev's questions must match the digest in the run's protocol.
Braces mark values filled in per fleet.

== The scenario
The public policy of Step 1's layout-0 episodes (a fleet's policy has one such paragraph per team):
#data-text("pr.policy")
The services text, the same for every team:
#data-text("pr.services")
The split team's three tasks, with each agent's read and write permissions:
#data-text("pr.tasks")

== The monitor (Step 1 and Experiment C)
The monitor's instructions, followed by the word EVIDENCE and the evidence as JSON: the policy and the given agents' tasks, tool calls, results and messages, with no run IDs or timestamps.
#data-text("pr.monitor")

== The monitor with search tools (Experiment A)
The monitor's instructions in Experiment A, followed by the policy, the services text, its calls so far with their results, and how many calls remain.
#data-text("pr.explorer")

== The graph tools (Experiment B)
Experiment B's instructions are Experiment A's, with this inserted before the finish line:
#data-text("pr.graph")

== Jev's questions (Experiment C)
Jev answers each question with a probability of yes:
#data-text("pr.jev")
One request in full: the backup agent's copy in the fleet of @app-flow's real example, as sent to Jev.
#data-text("pr.jev.request")

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
