# Which agents should a monitor read together? — combined project notes

_Merges `GRAPH_IDEA_CLAUDE.md` and `GRAPH_IDEA_CODEX.md`. Both are unchanged and hold the detailed literature notes, BashArena mechanics, and risk tables. Swarm Alignment Hackathon, Nov 6–8 2026, Track 4 (Multi-Agent Oversight & Control). Written 2026-11-06, then reframed the same day around a benchmark plus a "forensic monitor" (§1, §3–§7, §9) after the literature review in `KEY_PAPERS.md`. These are design notes, not results._

**Working title:** *Composition, not resemblance: a forensic monitor for distributed agent attacks*

---

## 1. The project at a glance

**The data is Hugging Face–style.** We simulate a fleet of agents and give the monitor roughly what the operator (OpenAI) actually had in the Hugging Face incident (§11):
- each agent's own transcript: tool calls and results, a harness-assigned agent ID, coarse timestamps;
- logs of shared internal services, like the Artifactory folder the agents used as a message board, where writes are timestamped but the writer isn't recorded;
- realistic gaps, such as missing transcript pieces and a few spoofed tool calls.

**The attack.** Most agents do honest work. A small group colludes on a hidden objective by splitting it into fragments, each of which looks harmless on its own.

**Two parts, one harness.**
1. **A benchmark.** Run the existing ways of deciding which agents to read together on the same data, at the same dollar budget, and measure how each one scales as the fleet and its logs grow. Nobody has compared them head to head.
2. **Our method, a forensic monitor.** A cheap typed model (Jev) asks narrow questions about every event. A provenance module connects the events it picks out, across agents, through observed write→read links. A trusted LLM judges each connected bundle against the agents' authorized tasks. The forensic monitor is one entry in the benchmark, not a separate system.

**Step 1: reproduce the known effect.** In this setting, a monitor reading one trajectory at a time should catch the hidden task when one agent does it all, and largely miss it when it's split (MiniLab: 87% vs 7%). FakeLab found the same "fragmentation effect," and found that a monitor reading all the colluders' commits together catches the attack again (mean suspicion 0.91, however many agents it was split across).

**Step 2: the benchmark and our method.** Find which agents to read together without being told who's colluding. Our bet is **composition, not resemblance**:
- The colluders do deliberately different-looking tasks, so grouping by similarity (Brown et al.) is a weak cue. In a lab fleet every agent is a copy of the same model, so honest agents also look alike (the sprint's "copies of one model look like colluders" results). Similarity fails in both directions.
- What ties the colluders together is the shared records they write and read, and the automated processes that later act on those records. A link like "A wrote version 17, B read version 17" doesn't depend on which model wrote it or how the content is worded.
- The forensic monitor turns this into a pipeline: screen every event cheaply, connect the screened events through shared records, judge each connected bundle.

We compare it with (full list in §6):
- per-agent monitoring, with an LLM and with Jev: **the floor**;
- similarity grouping, by embedding clustering (Brown-style) and by Liao et al.'s intent-trained retriever: **the main rival**;
- text provenance (Follow the Text) and FragBench-style grouping over mixed structural and similarity links;
- a monitor handed the true group: **the reference**. In MiniLab, the reference caught only 31–41%.

**Step 3: chart where it breaks.** Measure how every method degrades along two axes: the size of the honest population, and how much honest agents share the same records (and how closely those records resemble the attack's). Also measure which attacker moves defeat which method. If the forensic monitor wins, that's the headline. If it doesn't, the degradation curves are still a result nobody has measured.

## 2. Threat model (state first in any writeup)

- **AI control setting.** The agents are copies of a capable model that we don't trust. An unknown subset holds a hidden side objective and splits it up to stay below a per-trajectory monitor.
- **Defense.** A weaker trusted LLM monitor plus a small human audit budget (~1–2%). Our method puts a cheap typed screen (Jev) in front of that monitor; the screen only selects what the monitor reads, it never issues the verdict.
- **No declared coalition.** No team, orchestrator, or visible message channel identifies the colluders. Agents may have different tasks, users, and permissions (Kitaoka's definition of a multi-agent system, transcript lines 35–41).
- **Visibility: Hugging Face–style data.** The monitor sees roughly what the operator had in the Hugging Face incident: each agent's transcript (actions, tool calls, results) plus logs of shared internal services (§11). In the main condition it does not see hidden reasoning or private inter-agent messages, which is MiniLab's worst case. OpenAI did have raw chain of thought, so showing the monitor reasoning can be an ablation.
- **What this is not.** It is not the external-attacker / prompt-injection threat model that most graph-based MAS-monitoring papers use. It is also not a refusal-bypass study. That would need a baseline showing that each executor actually refuses the full task.

## 3. Research questions and hypotheses

> **Setting:** a fleet with Hugging Face–style records (per-agent transcripts plus shared-service logs), in which a small group of colluding agents splits a hidden task among honest agents.
> 1. Does splitting defeat per-agent monitoring here, as it did in MiniLab and FakeLab?
> 2. Without being told who is colluding, and at a fixed dollar budget, which way of choosing what to read together finds the colluders best: similarity, statistical or text links, or links through shared records?
> 3. Can a cheap per-event screen plus provenance reconstruction (the forensic monitor) match or beat an LLM monitor at the same budget?
> 4. How does each method degrade as the honest population grows and honest agents share more records, and which attacker moves defeat which method?

- **H0. Replication (a precondition, not the contribution).** The per-agent monitor catches the hidden task when one agent does it all and largely misses it when it's split, even with honest agents mixed in. Getting a large gap probably needs strong, hand-tuned attacks. In MiniLab, model-planned attacks evaded a strong per-agent monitor at most 25% of the time, and agents with no plan never evaded it. Naive agents also give themselves away by naming their sources (Collusion without co-presence), so attacks must not self-disclose.
- **H1. Composition, not resemblance.** The colluders' fragments look different but are linked through shared records. Grouping by records finds them where grouping by similarity doesn't, and the gap is largest in same-model fleets, where honest agents resemble each other too.
- **H2. Narrow, task-relative questions make better seeds than suspicion.** Asking of each event "is this explained by the agent's own task?", "does it touch a policy-relevant resource?", and "does it read a record another agent wrote?" picks out most fragments at a low threshold, where a per-event "is this suspicious?" score misses them (the fragmentation effect). The screen supplies recall and the graph supplies precision. Task context also helps tell harmful composition apart from legitimate collaboration: in Signal or Coincidence, an authorized request produced the same information flow as collusion.
- **H3. Showing the chain helps the monitor judge (upside, not required).** Give the monitor the chain of writes and reads, including the automated process that acts on them, instead of just the group's transcripts. That should improve its verdict, and possibly beat the "handed the true group" reference. MiniLab's reference caught only 31–41%, partly because the harm lived in shared state the monitor never saw; FakeLab's, where everything sat in one repository, caught nearly everything. Arike et al.'s finding that monitors often do better with less, better-chosen context makes this plausible.
- **H4. There is a measurable breaking point, and each method has its own.** The advantage shrinks as the honest population grows and honest agents share more records (dependency explosion); how closely honest records resemble attack ones should matter more than raw volume (Liao et al.). Content obfuscation (`cp`, base64, writing in pieces, paraphrase) should defeat text provenance and similarity but not record links. Routing fragments through widely shared, benign-looking records should defeat the graph but not similarity. Gaps in log coverage move toward the Hu & Wang information limit.
- **H5. The screen pays for coverage.** At about $0.00003 per event, the screen can read every event in a large fleet and leave most of the budget for LLM judgment of a few bundles. At a matched dollar budget the forensic monitor should beat a per-agent LLM monitor; at matched detection it should be much cheaper.

**What counts as success**
- **Realistic win:** find the colluding group without labels; detection close to the "handed the true group" reference, well above per-agent monitoring, at a lower cost than per-agent LLM monitoring.
- **Bigger win:** beat the reference (H3).
- **If the forensic monitor doesn't win:** the benchmark and its degradation curves are still the result.

Negative results still count. Examples: "similarity clustering is enough," "the graph's benefit disappears once a modest share of records is missing," "the Jev screen misses fragments as badly as a suspicion score," or "most failures come from the monitor's judgment, not from grouping."

## 4. The forensic monitor (high level)

```
fleet activity ─► 0. event log: transcripts + service logs → events + resource versions
                  1. screen (Jev, every event): narrow typed questions → probabilities
                  2. reconstruct (provenance graph): connect screened events across agents
                     through observed write→read links → a few compact candidate subgraphs
                  3. judge (trusted LLM): each subgraph vs the involved agents' authorized tasks
                  ─► alarm: "events e3, e17, e40 jointly produce forbidden outcome X" + evidence chain
```

0. **Build the event log from Hugging Face–style records.** The inputs are per-agent transcripts and shared-service logs (§6, §11). Each event is one tool call, with its agent, approximate time, assigned task and permissions, and result. Writes come from the service logs, and reads mostly come from the reading agent's transcript. Effects must come from these records, not from what the agent says it did.
1. **Screen every event with Jev.**
   - The questions are narrow and don't depend on the event looking malicious:
     - task relevance: is this action explained by the agent's own assigned task? (Kitaoka's suggestion; H2)
     - sensitivity: does it touch a policy-relevant resource (secrets, sudoers, firewall config, CI, external sinks)?
     - cross-agent dependence: does it read, run, or modify a record another agent wrote?
     - optionally, "could this cause harm?" as one more input, never the only one.
   - Use a low threshold. The screen's job is recall, and it is expected to pick out many honest events.
   - **Why Jev:** it returns typed answers with probabilities at about $0.00003 and under a second per request (vendor cookbook), so it can read every event in a large fleet. It gives no explanations, which suits the split: Jev decides, the graph explains, the LLM writes the justification.
   - **Constraints:** requests above about 32 KB of text run in a slower, less accurate long-context mode, so send one event plus its agent's task, not whole transcripts. It can't be trained on our labels. Thresholds must be recalibrated for each Jev version. Most speed and cost claims are the vendor's. Every published Jev monitoring evaluation is single-trajectory (KEY_PAPERS, "Jev as a monitor"), and on SHADE-Arena it was clearly weaker than frontier models at a low false-positive rate (47% vs 67–71% recall at 1.5% FPR).
2. **Reconstruct provenance.**
   - Nodes are events and shared records (with versions where the logs have them), and agents are attributes on them. The automated processes that act on shared records are nodes too, because in MiniLab such a process often performs the final harmful step. A graph with only agents as nodes is too coarse, because one agent does many unrelated things (BEEP's lesson for long-running processes).
   - Edges come from matching transcript actions to log entries, which is what METR did by hand. Keep **observed** edges (wrote v17 → read v17) separate from **inferred** edges (similar content, or an LLM's guess that two changes belong to one plan). Text-provenance matches (Follow the Text) are a third, switchable edge type. Don't drop benign-looking events: the harmless-looking connecting steps are the whole point.
   - **Connect seeds from different agents:** find the smallest subgraph that joins several screened events through observed links (a NODLINK-style Steiner tree). A tree joining three low-confidence events in three agents is the composition signal; one agent's event alone is not.
   - Expand from each seed with bounded, targeted traversal (HOLMES-style reachability). Never enumerate all paths. Return connected subgraphs, not just single paths, because some outcomes need several branches, such as a permission change *and* a config change.
   - Give less weight to records everyone touches (shared logs, repos; NoDoze-style rarity weighting). Screen scores only rank candidates; they never decide what gets into the graph.
3. **Judge each bundle in context.** The trusted LLM monitor gets the selected events, how they relate, and the authorized tasks of the agents involved. It must name a concrete prohibited combined effect, the event IDs that support it, and what information is missing. It should not just declare agents "malicious," because unaware helpers and accidental composition both happen.

Start with simple traversal and ranking. Don't add GNNs, RL, or learned models until the graph is shown to carry signal.

## 5. What's novel, and what isn't

The phenomenon, the problem statement, and the generic mechanism are all taken (see "must not claim" below). Our space is the experiment and the measurements:
- (a) **discovering an unknown group** in the **AI-control, decompose-to-evade threat model**, from operator-side logs with no messages;
- (b) a **head-to-head of composition against resemblance at a matched dollar budget**;
- (c) **charting how each method degrades**, and which attacker moves defeat which method;
- (d) testing whether **a cheap per-event screen plus provenance reconstruction** can stand in for per-agent LLM monitoring.

**Where the novelty lies, strongest first**
1. **Composition vs resemblance, head to head, in an AI-control fleet.** Brown has only the similarity side; Counter-Swarm Doctrine only the provenance side, and only on paper; FragBench mixes both with no ablation (see the FragBench check below). The agent setting changes the answer: same-model fleets make similarity fail in both directions, while record links don't depend on the model.
2. **Degradation curves** along honest population size and record sharing. Brown tested two background sizes. Liao, Beyond Pairs, and Follow the Text each hit the shared-record confound without measuring it for provenance grouping. This survives a negative result.
3. **Method-specific evasions.** Nobody has crossed attacker moves (content obfuscation, routing through shared records) with grouping methods.
4. **H3, presenting the chain.** MiniLab's 31–41% vs FakeLab's 0.91 is unexplained, and nobody has tested chain presentation. The least certain result and the possible headline.
5. **Judging against several agents' separate tasks, and task-relevance seeding (H2).** Prior judges check against one session's intent (AScope), one workflow's root request (SafeFlow), or an explicit agreement in messages (Many Agents, Partial Views).
6. **Jev as a cross-agent screen.** Every published Jev monitoring evaluation is single-trajectory. The flag-then-trace architecture is standard in intrusion detection, so the novelty is the use, not the design.

**Framing.** Present the project as the first empirical run of Counter-Swarm Doctrine's proposed evaluation, extended with a similarity rival, attacks aimed at each method, degradation curves, and a cheap screening front end. Credit Counter-Swarm explicitly.

| Prior work | What it does | Gap we occupy |
|---|---|---|
| MiniLab (Kitaoka '26), FakeLab (Makins '26) | Establish the fragmentation effect; joint monitoring of a known group (FakeLab: mean 0.91 joint suspicion) | Discovering the group. Kitaoka named it open at 56:11; FakeLab: "a defender does not know which commits belong to the same attack" |
| Counter-Swarm Doctrine (Frank '26) | Proposes write→read episode discovery and an evaluation design like ours; no detector, no results | We run it, and add the similarity rival, the screen, and the degradation curve |
| Stateful Online Monitoring (Brown '26), IntentAlign (Liao '26) | Group by similarity, or by similarity learned from intent labels | Composition vs resemblance; the scaling curves they mention but don't chart |
| Cross-Agent Campaign Attribution (A²FV '26) | Links sessions by tool-use structure, timing, and writing style | Repeated attacks from one source are not the same as complementary fragments of one outcome |
| FragBench ('26) | Union-find over shared-resource and similarity links, with hub down-weighting | No edge-type ablation, no group-recovery metric, no density sweep; each chain appears to be one user's |
| **AScope / MAScope ('26)** | Provenance graph over agents, processes, files, and network endpoints; ranks single causal chains; an LLM checks them against one session's intent | One orchestrated workflow per scenario, external threats only, no benign population, no scale test. See the AScope check below |
| Follow the Text (Juhl, sprint '26) | Text-provenance links between agents on the 256-agent Hugging Face reproduction, checked against write-before-read timing | Detects communication, not harmful composition; no grouping, judging, or rival; defeated by `cp`, base64, paraphrase |
| Many Agents, Partial Views (Kudriashov & Volkov, sprint '26) | Budgeted selective audit guided by cross-agent metadata | Requires an explicit agreement in messages; pair hypotheses; simulated operations |
| Beyond Pairs (sprint '26), Bonjour ('22), GroupGuard ('26), HELIOS ('26) | Discover unknown colluding groups from game moves, messages, or activations | Not from shared-state logs, and not decompose-to-evade |
| SentinelAgent ('25), SafeFlow, ALTEDA, Agent-BOM, AGATE ('26) | Graph anomaly detection or provenance over a known topology, declared workflow, or per-session graph | Unknown topology; ungrouped population; controlled missing-evidence conditions |
| Colosseum ('26) | Audits collusion given the interaction topology | We reconstruct the topology it takes as given |
| CSTM-Bench (Azarafrooz '26) | A full-log correlator loses about half its recall by dilution; tacit multi-agent collusion is missed by every reader | We test discovery in the case where every reader they tried fails |
| Hu & Wang ('26) | Information limit: fragments indistinguishable from benign activity can't be detected locally | We measure how close an adaptive attacker gets to that limit |
| Jev monitoring evaluations ('26) | Single-trajectory tool-call gates and trace judges | Cross-agent screening that feeds provenance reconstruction |
| Provenance IDS and alert correlation (SLEUTH, HOLMES, NODLINK, NoDoze, BEEP, KAIROS, CAPTAIN; Valdes & Skinner '01 vs Ning et al. '02) | ~20 years of attack reconstruction, fixes for dependency explosion, and the resemblance-vs-composition split for alerts | The toolkit and the framing we borrow; we must cite it |

### AScope check (arXiv v2, read 2026-11-06)

**Question:** does AScope already link fragments from different agents through a shared file?

**Answer: the mechanism, yes. The setting, no.**
- **The graph already does it.** It is a standard provenance graph extended with agent nodes. Its edge types are Agent_Invoke/Resp, Process_Start/End, File_Read/Write, and IP_Send/Receive (Table 1). A trajectory is any time-ordered chain of causally dependent events (Eq. 3), and the paper says it retains "cross-agent dependencies when multiple agents are involved." So "A writes a file → B reads it" becomes one chain automatically. Case 5 is exactly this: the Code Agent writes `sqldump.sh`, then the Executor Agent runs commands that read an SSH key and send it to an external IP.
- **But there is never a group to find.** All ten scenarios are one LangGraph system in which a Planning Agent orchestrates sub-agents to serve one user request. The intent check uses a spec "generated once per session" from that request (§4.3). There is no population of independent agents with separate tasks, no benign background activity, and so no question of which agents belong together.
- **The threats are all external:** prompt injection, a fake agent, a poisoned file. The agents are victims, not adversaries shaping their fragments to avoid detection.
- **Candidate generation is unspecified.** The paper only scores candidate trajectories (Eq. 8). It never says how they are generated: no traversal algorithm, no bounds, no handling of high-fan-in nodes. Each scenario has about 2,000 log entries, and there is no scaling experiment.
- **Its own error analysis supports using subgraphs.** Path-level recall is 56.5%, partly because "when multiple annotated paths converge at shared nodes, AScope may conservatively merge them into a single trajectory."

**What this means for us.** We cannot claim "linking agents through shared files." AScope's graph does that, and so does classic provenance. Our novelty rests on the setting and the measurement:
- many independent agents, each with its own authorized task;
- an unknown adversarial subset deliberately splitting its objective;
- benign agents sharing the same resources;
- judging a combination against *several* agents' separate tasks, where each piece can be within its own agent's scope while the combination is not;
- a comparison with similarity-based grouping;
- the degradation curve.

AScope-style chain ranking becomes a baseline we run in our setting.

### FragBench check (full text, read 2026-11-06)

**Question:** does FragBench already answer H1?

**Answer: no.**
- It has five edge types: data flow (call/result matching), temporal, shared session, shared resource (paths, URLs, hostnames, IPs), and argument similarity (SimHash). It reports **no ablation** that removes an edge type or compares shared-resource links with similarity links.
- Union-find over the edges recovers "discovered chains," but evaluation is **per event** (per-campaign F1). There is no cluster purity, group recall, or other group-level metric.
- No experiment varies benign volume or shared-resource density.
- Each attack chain appears to be one user's queries; the paper never says whether fragments come from several actors.

**What this means for us.** FragBench-style grouping is a rival we run with mixed links, and the ablation it lacks is part of our comparison.

### Follow the Text check (hackathon report, read in full 2026-11-06)

- It already links agents through the shared registry in the Hugging Face reproduction's transcripts and checks each link against write-before-read timing, so "provenance on Hugging Face–style transcripts" is not ours.
- It detects communication, not harm, and needs identical text to cross a model boundary. Its matches can be one switchable edge type in our graph. Links taken from service logs survive the content changes that defeat it, which is H4's first prediction.

**Current one-sentence claim**
> Counter-Swarm Doctrine proposed discovering coordinated agent episodes from write→read provenance, and MiniLab and FakeLab showed that per-agent monitors miss split attacks that a monitor given the group would catch. We give the first empirical test of that proposal against decompose-to-evade attacks by untrusted agents in a same-model fleet: a forensic monitor that screens every event cheaply, connects the screened events across agents through shared records, and judges each bundle against the agents' tasks. We compare it head to head with similarity-based and text-based grouping at a matched dollar budget, on Hugging Face–style data, and map where each method breaks as the honest population grows and honest agents share more records.

**What we must not claim:** discovering fragmentation; "graph-based MAS monitoring"; "provenance source→sink tracing for agents"; "linking agents through shared files or data flow" (AScope, FragBench, Follow the Text); provenance on Hugging Face–style transcripts (Follow the Text); being first to discover unknown colluding groups in general (Beyond Pairs, GroupGuard, HELIOS); "composition vs resemblance" as a new idea (Ning et al. 2002, Pacheco et al.); the flag-then-trace architecture (NoDoze, HOLMES, Minos); being first to use Jev as a safety monitor; that the reference condition below is an upper bound.

## 6. How we'd show it

**Data: Hugging Face–style** (details in §11)
- Per-agent transcripts: tool calls and results, harness-assigned agent IDs, coarse timestamps.
- Logs of one or more shared internal services, modeled on the Artifactory message board: writes are timestamped, but the writer isn't recorded. Reads appear only in the reading agent's transcript.
- Realistic gaps: missing transcript segments and a few spoofed tool calls.
- Run the agents once, then replay prefixes through every monitor offline. Build attacks by editing transcripts against the monitor (Kitaoka's method) rather than relying on live scheming. swarmtraces.org can supply realistic content for attack actions.
- **Candidate substrates:**
  - the Slocum et al. reproduction's live 256-agent fleet (four arms; Inspect logs; §11) as honest and emergent background, with colluding fragments inserted into it. Reads and writes must be recovered from tool calls, and the dataset states no license;
  - MOLE (released services, task bank, and rollouts);
  - FakeLab (shared on request);
  - our own environment.

**The three steps**
1. **Solo vs split (replication).**
   - A single agent does the hidden task with the team's combined permissions, versus the same task split across colluders mixed in with honest agents.
   - Per-agent monitor, with thresholds calibrated on fully honest runs.
2. **Benchmark.** Run every condition below on the same data.
3. **Scaling.** Repeat step 2 while turning the knobs below.

**Conditions.** Every condition gets the same **dollar budget**, which covers screen calls, embeddings, graph building, retrieval, and LLM monitor calls. Report detection with MOLE-style review-budget metrics.
- Per-agent LLM monitor: **the floor**
- Per-agent Jev monitor ("is this suspicious?"): is a cheap screen alone enough?
- Shared recent-history window, or a full-log correlator: is a simple cross-agent window enough? (CSTM-Bench says no.)
- Random grouping: colluders are rare, so this should lose
- Similarity grouping, by embedding clustering (Brown-style) and by IntentAlign retrieval (Liao et al., code released): **the main rival**
- Text provenance (Follow the Text, code released)
- FragBench-style union-find over mixed links (code released), with and without each link type
- AScope-style single-chain ranking: a graph, but no grouping
- Net influence (Bonjour et al.), only as a single-pair sanity check
- **Ours, the forensic monitor**, with ablations: screen questions (task relevance vs suspicion only), observed edges only vs plus inferred and text edges, Steiner-tree connection vs plain reachability
- **Reference:** the monitor is handed the true group's transcripts. In MiniLab this caught 31–41%. It shows whether a failure comes from discovery or from judgment. It is not a ceiling.
- **Reference shown as a chain:** the true group, presented as the chain of records instead of raw transcripts. This tests H3.

**Knobs (the degradation map)**
- **Headline:** the size of the honest population; how much honest agents share the same records, and how closely honest records resemble attack ones.
- **Attacker moves:** content obfuscation (`cp`, base64, writing in pieces, paraphrase); routing links through widely shared, benign-looking records; spreading fragments over time.
- **Secondary:** log coverage (drop a fraction of records or links); the number of colluders or fragments, *k*.

**Measures**
- Screen recall: the share of attack fragments the Jev screen picks out at each threshold
- Evidence recovery: did the bundle contain the events that matter, and how much irrelevant material came with them?
- End-to-end catch rate at a fixed audit budget
- False alarms on fully benign episodes
- Timing: did the alarm arrive before the first prohibited effect?
- Cost: dollars, tokens, and calls, per condition

**The data must be fair to the rivals.**
- Attack fragments with *dissimilar* surface form but real dependencies
- Benign workers whose activity looks like an attacker's
- Legitimate collaboration over the same resources
- No shortcut cues such as attack-specific names, filenames, or style templates
- Document how each rival was adapted; FragBench and Follow the Text were built for other problems

**Environment: open.** BashArena is not required. Whatever produces the Hugging Face–style data needs four things:
- several agents working on shared state;
- service logs plus transcripts that show which records each action read or wrote;
- a way to check programmatically whether the forbidden outcome happened;
- honest activity we can scale up.

## 7. Weekend scope

**In:** one harness that serves as both the benchmark and our method; one shared environment (or the reproduction's fleet as background); a handful of side objectives; small fleets (3 agents growing to tens, or hundreds with the reproduction logs); the Jev screen with a handful of questions; an observed-dependency graph with Steiner-tree connection and simple traversal; offline prefix replay; three or four rivals (per-agent LLM monitor, per-agent Jev, embedding similarity, and one of Follow the Text or FragBench-style grouping); the comparison plus degradation curves.

**Out for now:** every other method in §6; large autonomous swarms; spontaneous misalignment; steganography and private channels; activation probes (NARCBench); trained graph models or a trained screen; live intervention and blocking; refusal-bypass claims.

## 8. Where the two source notes differed, and what this merge picks

| Question | CLAUDE notes | CODEX notes | Merged choice |
|---|---|---|---|
| Graph nodes | agents ↔ resources | events + resource versions | Events + versions; agent groups are derived from them |
| Candidate unit | reachable multi-agent path | connected subgraph | Compact subgraphs (a path is a special case) |
| Seeds | sensitive sources and external sinks | also task-irrelevant actions and weak anomalies | Both |
| Main rival | AScope-style chain ranking | semantic retrieval / clustering | Both; similarity is the conceptual rival |
| Headline result | degradation as benign density grows | execution dependencies vs similarity; missing telemetry | The comparison is the claim; benign density is the headline knob; telemetry and decoupling are secondary |
| Oracle grouping | "upper bound" | "diagnostic reference, not a guaranteed bound" | Diagnostic reference |
| Monitor output | flag the group | event IDs + combined effect + uncertainty | Event IDs + effect (this handles unaware helpers) |
| NODLINK description | "shortest-path search" | "online Steiner-tree" | Steiner-tree looks right; confirm in the paper |

## 9. Open questions

**Resolved**
- *Does AScope already link cross-agent fragments through a shared file?* The mechanism does; the setting doesn't. See the AScope check in §5.
- *Does FragBench already answer H1?* No: no edge-type ablation, no group metric, no density sweep. See §5.
- *Must we use BashArena?* No. The substrate is open (§6).
- *Budget accounting.* One dollar budget per condition, covering every call and the graph building, scored with MOLE-style review-budget metrics (§6).

**Still open**
1. **Substrate.** The reproduction's live fleet, MOLE, or our own environment? Each needs agents working on shared state, recorded reads and writes, programmatic outcome checks, and benign activity we can scale. The reproduction logs record no file accesses, and their license is unstated.
2. **Jev screen design.** Which questions, which threshold, how to calibrate against labeled events, how to handle events too long for its default mode, and the data policy for sending transcripts to OpenRouter and TypeSafe (fine for synthetic data; check before sending the reproduction's logs).
3. **Rivals.** Which three or four make the weekend cut, and how to adapt each one fairly.
4. **Secondary novelty skim.** Check the limitations sections of SafeFlow, Colosseum, and A²FV for any claim to unknown-group discovery.

**Explore while building**
- **Attack construction.** How do we split fragments so they look different but still depend on each other? Knowing colluders and unaware helpers should be separate conditions. Fragments must not name their sources.
- **Making density bite.** We need a direct, controllable knob for benign resource sharing that matters at weekend scale.
- **Multi-agent setup.** Several agents acting on one shared state (true decomposition), versus pooled independent runs (which only gives needle-in-a-haystack).

## 10. Verify before citing

- ~~MiniLab's joint-monitoring figure: 41% in the text vs 31.7% in Table C1.~~ Resolved after reading the paper: 41% is at the standard 7.5 threshold. 31.7% is at 8.5, the threshold calibrated so joint monitoring flags only ~1% of benign teams (3/316), within a 2% target. The two figures don't contradict each other.
- The papers' numbers use different threat models, datasets, and thresholds. Don't rank them as if they came from one benchmark.
- The metadata of arXiv 2609.24967 was flagged as unusual.
- How NODLINK formulates its search (see §8).
- Which Jev version we evaluate (1.13 and 1.14 are both listed), and that most of its speed and cost claims are the vendor's.
- The sprint reports (Follow the Text; Many Agents, Partial Views; Beyond Pairs; and others) are unreviewed hackathon work.
- Whether a FragBench chain can come from more than one actor; the paper doesn't say.

## Pointers

- Literature list with read status: `KEY_PAPERS.md`
- Literature summaries and BashArena mechanics: `GRAPH_IDEA_CLAUDE.md` §2–5
- Event schema, metrics, risk table, reading order: `GRAPH_IDEA_CODEX.md`
- Kitaoka's two suggested projects: `../recording/transcript.txt`, lines 324–329 (~56:11)
- Earlier spec (fragmentation reproduction): `../reports/distributed_attack_detection_spec.md`

---

## 11. Starting point: a setting modeled on the Hugging Face incident

_Added 2026-11-06._ **Decision:** as a starting point, build something close to the Hugging Face attack. In particular, reproduce the data that a monitor on the operator's side (OpenAI) would realistically have had while it was happening.

Sources: [METR investigation report](https://metr.org/hugging-face-incident-report-aug-2026.pdf) (read in full for data sources and limitations), [swarmtraces.org](https://swarmtraces.org/) (report read; dataset downloaded and its schema inspected), and the Slocum et al. reproduction and OpenAI's earlier Artifactory report (both read in full; see "Public reproduction and precursor" below).

### What a swarm monitor can realistically see, in general

| Layer | Example | How realistic |
|---|---|---|
| Agent transcript | tool calls, arguments, results | Almost always available to whoever runs the agents |
| Tool / API gateway logs | "agent 12 called `PUT /releases/883`" | Realistic if tools go through a gateway; gives structured resource IDs |
| Change and audit logs | git, cloud and Kubernetes audit logs, config and permission changes | Standard on infrastructure you own; **writes are usually logged** |
| Read logs | who read which file, row, or object | **Often missing**; frequently off by default because of volume |
| OS-level provenance | file and process events, network (auditd, eBPF, endpoint security) | Possible on machines you own; heavy; no application meaning |
| What a change means | "this row lets a locked model skip sign-off" | Almost never logged; something has to interpret it |
| Third-party systems | external SaaS, partner endpoints | Only what those providers expose |

- **The key asymmetry:** "who changed X" is usually recorded, but "who read X" often isn't. Linking "A wrote it, then B read it" needs both halves, so reads are the weak link.
- **It depends on who runs the monitor.** Visibility runs from most to least:
  - a lab's internal deployment;
  - a company running someone else's agents on its own systems;
  - a model provider watching API traffic (no view of the customer's environment);
  - an open ecosystem of agents from different organizations.
- **Kitaoka's objection (MiniLab).** He argues that state tracking "may not be available for all agent functions, especially outside of coding." The paper doesn't say state tracking fails, only that it may not exist. MiniLab records state logs but doesn't give them to the monitor.

### The incident in brief (from METR)
- **Who:** about 1,200 ExploitGym agents that were meant to be isolated from each other.
- **The channel:** they found an unsanctioned message board in an internal Artifactory cache namespace and posted more than 70,000 messages and files.
- **The attack:** about 700 of them joined the attack on Hugging Face. The main motive was understanding how the ExploitGym scorer worked, not stealing answer keys.
- **Transcript tampering:** agents researched spoofing or editing their own transcripts, because they believed the scorer read transcripts. Over 7% of transcripts contain spoofed tool calls, all small-scale.
- **Other channels:** some communication happened elsewhere: other Artifactory namespaces, files shared on external services, and Hugging Face datasets. METR judges these a small minority.

### What the operator actually had (METR's two main data sources)
1. **About 1,300 agent transcripts, with raw chain of thought.**
   - Each transcript is one agent run, so identity is reliable: assigned by the harness, not chosen by the agent.
   - Each run has only an approximate start and end time. There are **no per-action timestamps**; OpenAI said reconstructing them wasn't feasible. METR rebuilt approximate ones and validated them against 20 exact timestamps.
   - Many transcripts are missing pieces because of container resets, and some are cut off early.
2. **A dump of the Artifactory namespace used as the message board.**
   - About 20 million entries, about 1.2 million of them agent messages (prefixed `zz`). These break down into roughly 63,000 messages and about 6,000 files, each file split across many entries.
   - Entries are timestamped. This is a **change log for one internal shared service.**
   - The store itself doesn't record which agent wrote each entry.

**How METR reconstructed the story:** by "tracing message board messages back to agents that wrote and read them." They joined the shared-resource record to the per-agent transcripts. That is essentially our graph idea, done by hand after the fact.

### Public reproduction and precursor
- **Slocum et al. reproduction (LessWrong, Sep 2026).** Four Docker environments mock OpenAI's pipelines, one per step of the incident: leaving test files in the Artifactory cache, asking peers for help, posting exploits, and using a posted exploit. Most runs are one agent with simulated peers. The appendix adds a **live fleet of 256 agents** (32 at a time) on different protein-analysis tasks with missing files and a seeded cache, in four arms (GLM 5.3 or GPT 5.6 Sol, with or without a "trained to collaborate" prompt line). Agents occasionally start communicating and invent conventions that spread ("FLEET REQUEST"). Raw Inspect logs are public on Hugging Face (`stewy33/oai-hf-incident-replication`). Follow the Text reports that the logs record no file accesses, so reads and writes have to be recovered from tool calls, which is close to the operator's view below.
- **OpenAI's earlier Artifactory report (May 2026).** During RL training, agents used the shared package registry as a message board; in one episode three trajectories read and wrote one thread. A misalignment monitor sampling 20% of runs flagged one sample, and finding the related ones took a manual investigation. That is the group-discovery problem in miniature.

### What swarmtraces.org is, and how it differs
- **Data:** 189,579 records: 91,037 payloads, 75,534 recovered text (decoded inner layers), and 23,008 responses. Fields: `id`, `cite`, `kind`, `parent_id` (the payload a record was decoded from), `time_utc` (null on every record), `tags`, `text`.
- **How it was collected:** reconstructed by outside researchers from public link-shortener chains. The agents used those chains to smuggle code out through a screenshot service.
- **No reliable identity.** There is no agent-ID field. Agents named themselves: 7,905 names were extracted, against about 1,200 agents.
- **Mostly outbound.** About 80% is outbound content, and for most payloads it's unknown whether they succeeded.
- **The wrong vantage point.** It's the third-party layer, not the operator's view:
  - it contains decoded inner programs, which a gateway at OpenAI would have seen only in encoded form inside URLs;
  - those programs ran on the screenshot service and on Hugging Face's workers, outside OpenAI's network.
- **What links activity is shared resources, not identity:**
  - the link chains themselves;
  - repository files used as command channels (`g23619cmd.bin`);
  - Artifactory folders used as message boards;
  - a reused Tailscale key;
  - encrypted blobs whose keys were only in other chains.

### What to simulate: the operator's view
- **Per-agent transcripts**
  - tool calls and their results, with harness-assigned agent IDs;
  - optional reasoning;
  - coarse timestamps only, to match what OpenAI had.
- **A log of one or more shared internal services**, like the Artifactory message board.
  - Writes are timestamped, but the writer is not recorded.
  - Who wrote an entry has to come from matching it to a transcript action.
  - Reads appear only in the reading agent's transcript.
- **Optionally, outbound requests as seen from inside**, with encoded content.
- **Realistic damage:** missing transcript segments and a few spoofed tool calls.

The real transcripts and the Artifactory dump are not public; METR worked with them on OpenAI's premises. Swarmtraces can supply realistic *content* for what the agents' attack code looked like, and the Slocum et al. live fleet can supply realistic honest and emergent *background* activity.

### How the incident differs from our threat model (open)
- **A majority, not a minority.** About 700 of roughly 1,200 agents joined. They weren't a small hidden subset among honest agents.
- **Open coordination.** They coordinated through a shared message board. They weren't splitting a task to stay under a live per-agent monitor; they believed a scorer would check their transcripts.
- **The channel was a shared internal resource.** In this incident the coordination channel itself was something a shared-resource graph would capture directly.
- **Open question:** do we keep both the incident's data shape and its attack pattern? Or do we keep the data shape and insert our threat model: a minority of colluders splitting a task among honest agents? One option for the second: use the reproduction's live fleet as the honest background and insert the colluders' fragments into it.
