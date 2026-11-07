# Key papers: closest work

_Last updated 2026-11-06. The tag after each link says how much of the paper we've actually read. Entries marked **hackathon report** are unreviewed submissions to Apart's AI Collusion Research Sprint (Oct 23–25, 2026); cite them as such, and expect that judges of this hackathon may know them._

**Sections**
1. Core: read all of these before writing the related-work section
2. Mechanism-adjacent: cite and distinguish
3. Also close
4. Apart AI Collusion sprint (Oct 2026): hackathon reports
5. Threat model and decomposition lineage
6. Methods and background (provenance IDS, alert correlation, monitor inputs, Jev as a monitor, cross-field precedents)
7. Setting and data
8. Scoped out, cite in one sentence

## Core

_Papers that already do some part of step 2 in GRAPH_IDEA.md §1 (finding which agents to read together from the records they share) or that supply the setting we replicate. Every entry here has been read in full or in its main sections; the tags say which._

**Counter-Swarm Doctrine: Containing Coordinated Agent Intrusions**
Gregory N. Frank (Sep 2026; position paper)
https://arxiv.org/abs/2609.06140 _(abstract and full text: sections 3–5 and appendices C–D)_
- **Shows:** Motivated by the Hugging Face incident, it frames the defender's problem as "prospective episode discovery": finding which actions belong together before anyone supplies group membership. The linking mechanism is ours: "A write links a run to an artifact version; a read links that version to a later run." Discovery starts from a seed (an out-of-scope operation, a canary read, a prohibited read, or a monitor alert) and retrieves time-respecting write–read paths within declared depth and review-size limits. Its proposed evaluation compares isolated actions, a rolling window, known-group review, and discovered episodes at matched false-alert workload, with independent agents on similar tasks and ordinary cache use as negative controls. It places storage-mediated coordination under stigmergy.
- **Gap:** It explicitly claims no detector and reports no results; the evaluation is a design. It cites FakeLab and coordinated-network detection but not MiniLab, Brown, AScope, or any provenance IDS. We are, in effect, running the experiment it proposes and must say so. Our additions are the provenance toolkit, the similarity rival, the task-relevance seeding, and the degradation curve.

**Red-Teaming Multi-Agent Attacks for Loss-of-Control Risks** (MiniLab)
John Kitaoka, Thao Amelia Pham, Carlos Rafael Giudice, Jacob Merizian (Oct 2026)
https://arxiv.org/abs/2610.24052 _(read in full)_
- **Shows:** In a simulated AI lab, splitting a hidden task across agents drops per-agent detection from 87% (one agent doing it all) to 7%. Even a monitor handed the whole colluding team catches only 31–41%.
- **Gap:** It assumes you already know who the colluders are, and it names finding them without that knowledge as future work.

**Multi-Agent AI Control: Distributed Attacks Hamper Per-Instance Monitors** (FakeLab)
Oliver Makins, Orazio Angelini, Zohreh Shams, Mary Phuong (UK AISI / MATS; Jul 2026, v2 Oct 2026)
https://arxiv.org/abs/2607.07368 _(v2: sections 1–4 and appendix C.4.3)_. Environment and trajectories shared on request; not open-sourced.
- **Shows:** Coding agents run in sequence on a synthetic AI-lab monorepo: 9 services, 86 benign main tasks, and 4 side tasks (disable monitoring, data poisoning, privilege escalation, weight exfiltration). State passes only through committed code, and no agent has the write permissions to finish a side task alone. A per-commit monitor sees only that agent's git diff and main task. As the attack is split across K = 1, 3, 9 agents, peak suspicion falls (the "fragmentation effect"); the paper attributes this to more plausible cover stories rather than dilution by benign code. The key control: squashing a sequence's commits into one diff gives a joint suspicion of mean 0.91 (range 0.65–1.00), flat in K and low on honest sequences. A planner with an unmonitored channel raises side-task completion up to 7×. Monitor quality dominates: going from GPT-5 mini to GPT-5 nano multiplies the odds of undetected success by 52.9 at 5% FPR.
- **Gap:** It states our problem as open. The joint monitor "is not deployable in practice: a defender does not know which commits belong to the same attack and so cannot assemble them into a single diff," and "it is not clear how to choose what context to include given a limited monitor compute budget." Agents run sequentially (parallel deployment is future work), the only channel is code, and there is no benign population beyond each sequence's own main tasks. Its joint-monitor result is far stronger than MiniLab's 31–41%; the contrast (one repository vs harm in shared state the monitor never saw) supports our H3. Appendix C.4.3 argues that handing a per-commit monitor the full repository state would not close the gap in real deployments.

**Stateful Online Monitoring Catches Distributed Agent Attacks**
Davis Brown, Samarth Bhargav, Arav Santhanam, Kasper Hong, Ivan Zhang, Matan Shtepel, Steffi Chern, Alexander Robey, Eric Wong, Hamed Hassani (UPenn; May 2026)
https://arxiv.org/abs/2605.31593 _(read in full)_
- **Shows:** It clusters agent sessions by similarity in real time and has an LLM review suspicious clusters. This catches attacks split across user accounts better than per-agent monitoring: 65.8% vs 55% recall with 100× benign traffic, at the same false-positive rate.
- **Gap:** It links fragments by how similar they look, which breaks when attackers rename files or change vocabulary. It also tested only two background sizes (10× and 100×), noting that the advantage narrows as benign traffic grows. This is our main rival.

**FragBench: Cross-Session Attacks Hidden in Benign-Looking Fragments**
Astha Mehta, Niruthiha Selvanayagam, Cedric Lam, Hengxu Li, Phuc-Nguyen Nguyen, Raymond Lee, Olivia McGoffin, My (Isabella) Luong, Arthur Collé, Jamie Johnson, David Williams-King, Linh Le (May 2026)
https://arxiv.org/abs/2605.11029 _(methods, evaluation, and limitations)_. Code: https://github.com/LidaSafety/fragbench
- **Shows:** It reconstructs fragmented attacks across sessions using a graph of tool-use events, linked by call/result flow, session order, shared resources, and argument similarity. Weighted union-find discovers connected groups, with common resources downweighted to avoid spurious hubs. A trained detector classifies the activity. This directly overlaps with our proposed group discovery and combines structural and similarity signals.
- **Gap:** The released benchmark evaluates event scoring, so its reported performance does not establish reliable recovery of hidden coalitions from incomplete operator logs. The authors also acknowledge that generated benign activity may differ statistically from attack activity in unintended ways. Its mixed structural-plus-similarity graph is a natural extra condition in our comparison.

**Cross-Layer Semantic Flow Reconstruction for Attack Detection in Agentic Systems** (AScope)
Qizhi Cai, Yangyang Wei, Zhipeng Chen, Shouling Ji, Zhenyuan Li (Zhejiang Univ.; Mar 2026, revised Aug 2026)
https://arxiv.org/abs/2603.04469 _(read in full)_
- **Shows:** It builds a graph of which agents read and wrote which files, processes, and network connections, then has an LLM check the highest-risk chains. This catches attacks that look harmless step by step (66.7% path-level F1 across ten scenarios).
- **Gap:** Every scenario is one orchestrated system attacked from outside, so it never has to find a hidden group of colluders among independent agents. It also isn't tested at scale. By this file's own definitions it is mechanism-adjacent; it stays in Core because AScope-style chain ranking is a baseline we run and because it sets what we can't claim.

**Follow the Text: Channel-Agnostic Detection of Inter-Agent Communication via Provenance** (hackathon report)
Daniel Juhl (independent, with Apart Research; Oct 2026)
https://pys8vc40ox3z7qxp.public.blob.vercel-storage.com/submissions/ai-collusion-research-sprint-2026-10-23-to-2026-10-25/Follow-the-Text-Channel-Agnostic-Detection-of-Inter-Agent-Communication-via-Provenance-dLtwuXqmrmVUT67mERTlV6qeEkM8ej.pdf _(read in full)_. Code: https://github.com/Scrattlebeard/source-provenance
- **Shows:** It builds agent-to-agent edges from text provenance. Every string an agent reads is indexed by its first origin, using 8-word, 40-character, and 20+-character "atom" shingles. A read fires when the text first appeared in another run, reached the reader by a different route, has a single origin, and was emitted by a model before the read. Findings are labeled authored (A wrote it, B read it) or relayed (A read a resource and passed it on). Each check is one lookup per shingle, with no pairwise agent comparisons. On the raw transcripts of Slocum et al.'s live 256-agent Hugging Face reproduction (four arms), 93–99% of detected edges are backed by a prior registry write from the origin agent, and it recovers 76–100% of the agents the reproduction's scorer flagged as broadcasters. In a rig with inotify ground truth (up to 15 sequential agents sharing one folder), it raises 1 false finding in 20 isolated episodes and has relayed-handoff recall of 0.91–0.92 at precision ≈1.0. On honest Refactor Arena runs it raises 55 false findings per 1,000 inputs, mostly test output shared by samples of the same repository. On DseWiki, 38% of edges join agents whose activity never overlapped in time.
- **Gap:** The nearest prior work on our exact data shape: it already links agents through a shared registry in Hugging Face–style transcripts and checks edges against write-before-read timing. But it detects communication, not harmful composition. There is no task-relevance judgment, no grouping into candidate subgraphs, no similarity rival, and no adversary splitting a task. It needs identical text to cross a model boundary, so `cp`, base64, writing in pieces, or paraphrase defeat it (a scripted white-box evader succeeded with 4 of 6 strategies). Ground truth exists only in the small rig. Its text-provenance edges could be one observed edge type in our graph, and its same-repository false positives are our "honest agents share records" knob in miniature.

**Many Agents, Partial Views: Auditing AI Collusion at Scale with Limited Information** (hackathon report)
Sergei Kudriashov, Sergey Volkov (SLAI, CUHK-SZ; Oct 2026)
https://pys8vc40ox3z7qxp.public.blob.vercel-storage.com/submissions/ai-collusion-research-sprint-2026-10-23-to-2026-10-25/Many-Agents-Partial-Views_Overleaf-SWFpgqpBfbD3GraPBEhFsxfBNOjNiN.pdf _(main text and appendix A)_
- **Shows:** Two separately evaluated steps.
  - A population screen over numeric market actions (up to 4M simulated agents in 200,000 known markets) removes shared behavior before scoring pairwise links. Same-model LLM sellers in *different* markets match each other's prices 9–15 times in 59 rounds, against about once by chance, so an unconditioned detector ranks independent cross-market pairs above the true pair.
  - CertAudit: the auditor sees only log metadata (record IDs, order, actors, recipients, types, object references, cost) and pays to reveal record text until a pair hypothesis is supported, refuted, or left insufficient. In TeamOps-L (8- and 12-agent teams with messages, simulated operations, and an approval ledger), complementary-group selection finds a valid evidence set in 82.9% of positives at 20% disclosure, against 1/111 for random search, reading about 17 of 90–145 records (AUROC 0.96). Shuffling the cross-agent metadata links drops AUROC from 0.953 to 0.755 on its synthetic test. Negative controls include benign cooperation, independent violations, valid permission, and abandoned plans.
- **Gap:** The closest existing treatment of step 2 as a budgeted search, and evidence that cross-agent link structure carries signal. But collusion is defined as an explicit "aware" proposal and acceptance in messages, which our threat model excludes. Candidates are pairs, the screen works only within known markets, operations are simulated, and the two steps were never combined. LLM readers gave 6–7.6% false supported verdicts. Its evidence standard (proposal, acceptance, executed operations, no waiver) is a template for our monitor's output, minus the message requirement. Its same-model price coincidence is direct evidence for H1.

**MOLE: Detecting Insider Threats in AI Agents**
Aashiq Muhamed, Virginia Smith (Sep 2026)
https://arxiv.org/abs/2609.06966 _(abstract and full-text sections on threats, observability levels, and metrics)_
- **Shows:** A benchmark of 150 AI-operated accounts sharing 9 stateful services over 30 workdays, with 12 harmful objectives hidden in routine work. Monitors get service-call traces at three cumulative observability levels: audit events (account, time, service, action, resource, arguments), plus tool results, plus agent reasoning. Labels are hidden; each monitor scores account-days, and a review budget of top-K accounts per day sets the metrics (recall at 10 reviews per day, budget-AUC). The best of 40 monitors still missed about half of completed harm. Two threats are collusive and split across two accounts over several days: one where both accounts independently approve a checkpoint to satisfy a two-signoff gate, and one where one account stages weights in a shared folder and the other exfiltrates them. The handoff runs through shared service state, not messages.
- **Gap:** Monitors score one account at a time; the only cross-account signals are peer-group baselines and a resource co-access feature. There is no group discovery and only two colluding pairs. It is the closest existing substrate to our "operator's view" data and it settles our budget-accounting question. The paper says code, the task bank, and the RQ1 rollouts are released; check the repository before building our own services.

## Mechanism-adjacent: cite and distinguish

_Same mechanism as ours, a graph over agent activity checked by an LLM or a gate, but a different problem: a declared or orchestrated workflow, an external attacker, a single agent, and no hidden group to find. These occupy phrases we can't claim ("graph-based MAS monitoring", "provenance tracing for agents"). Cite them for that reason and distinguish on setting; none starts from an ungrouped population or measures degradation._

**SafeFlow: Semantic Information-Flow Control for Blocking Malicious Propagation in Multi-Agent Systems**
Haowen Dai, Zonghao Ying, Wenfeng Li, Xiangfan Wu, Yisong Xiao, Tianyuan Zhang, Jiaye Lin, Lei Wei, Guangyuan Dong, Xitong Ling, Xixun Lin, Quanchen Zou, Xiangzheng Zhang (Jul 2026)
https://arxiv.org/abs/2607.25255 _(methods and boundary-condition sections)_
- **Shows:** It tracks risk labels across agents and reconstructs upstream context before checking the combined workflow. Its motivating example is sensitive information retrieved by one agent, rewritten by another, and sent by a third: locally plausible steps that jointly violate policy. It explicitly examines missing provenance edges as a failure case.
- **Gap:** It operates inside an instrumented workflow with a root request, planner, and observable dependencies. It does not establish reconstruction of an unknown coalition from partially unattributed logs across independent tasks.

**Beyond the Prompt: Log-Based Threat Detection and Attribution for Multi-Agent LLMs** (ALTEDA)
Elnaz Rabieinejad, Fattane Zarrinkalam, Ali Dehghantanha (2026)
https://www.sciencedirect.com/science/article/abs/pii/S0306457326001597 _(publisher abstract and section excerpts; full text inaccessible)_
- **Shows:** It synchronizes application, network, and system logs, builds an attributed interaction graph for each run, detects compromise, and attributes the detection to agents and interactions. It uses no prompt or response text and evaluates early detection from partial traces.
- **Gap:** Its described evaluation classifies individual workflow sessions under instruction-based attacks. It does not establish discovery of an unknown colluding group across an initially ungrouped fleet.

**SentinelAgent: Graph-based Anomaly Detection in Multi-Agent Systems**
Xu He, Di Wu, Yan Zhai, Kun Sun (May 2025)
https://arxiv.org/abs/2505.24201 _(abstract and key sections)_
- **Shows:** It models a multi-agent system's execution as a graph, which lets an LLM overseer flag problems at the agent, message, and path level, including collusion. The evidence is two case studies: an email assistant and Magentic-One.
- **Gap:** It starts from the system's declared architecture and catches collusion by matching known attack-path patterns. So it can't find an unknown group or a new way of splitting a task, and it has no quantitative evaluation at scale.

**Towards Security-Auditable LLM Agents: A Unified Graph Representation** (Agent-BOM)
Chaofan Li, Lyuye Zhang, Jintao Zhai, Siyue Feng, Xichun Yang, Huahao Wang, Shihan Dou, Yu Ji, Yutao Hu, Yueming Wu, Yang Liu, Deqing Zou (May 2026, revised Oct 2026)
https://arxiv.org/abs/2605.06812 _(revised abstract only; HTML body incomplete)_
- **Shows:** It organizes fragmented execution evidence into a graph connecting capabilities, runtime states, actions, and propagation between agents. Its audit procedure locates an entry point, traces backward and forward, and checks security attributes to reconstruct attack chains.
- **Gap:** The verified description supports attack reconstruction and auditing, but does not establish discovery of deliberately colluding subsets from incomplete logs. It is especially relevant to our evidence schema and explanations; its evaluation needs a full-text review.

**Structurally Close, Temporally Distant: Measuring Security Exposure in Long-Horizon LLM Agents**
Md Jafrin Hossain, Nur Al Hasan Haldar (Univ. of Western Australia; Sep 2026, under review)
https://arxiv.org/abs/2609.05911 _(read in full)_
- **Shows:** Builds a per-trajectory graph over AgentDojo events with sequence edges plus four deterministic provenance rules: a state-key write joined to a later read of that key ("a lookup, not an inference"), exact typed-identifier matches, tool calls batched in one message, and a tool call joined to its result. Influence distance is the shortest path from an injected input to a sensitive sink; sequence distance is the step gap. Across 454 pairs from 360 trajectories on 4 models, the structural path is shorter than the time gap in 96.9% (median 12 vs 23 steps), so time order hides structural closeness. A gate that blocks at influence distance ≤ 2–3 catches 5 extra attack sinks with no extra benign blocks (p = .0625). The gap does not predict attack success.
- **Gap:** One agent, external injection, sinks fixed by tool name; the authors "measure candidate influence pathways rather than causal attribution." Code promised on acceptance. Useful as a clean single-agent version of our observed-edge graph and as the argument that a rolling time window (our shared-history baseline) misses structurally linked events.

**AGATE: Provenance-Based Runtime Defense Against Compositional Attacks on LLM Agents**
Xiaorui Zhang, Zhuoran Cheng, Kailin Liu, Zhaoxi Sun, Shiyu Fan, Tongyu Yuan, Bin Yuan, Weizhong Qiang, Deqing Zou (Sep 2026)
https://arxiv.org/abs/2609.30830 _(abstract only)_
- **Shows:** Puts a deterministic authorization and data-provenance gate at the harness boundary of three agent frameworks: delegated actions are limited by parameter-bound, expiring grants, an effect ledger tracks repeats, and every decision is stored with evidence so runs replay for forensics. Names its own limits as transformed content, legitimate reuse, and observation coverage.
- **Gap:** One agent, one harness, external compositional attacks, and no cross-agent linking. Marginal; keep it as the reference for what a gateway log can and cannot capture, and because its three stated limits map onto our knobs (inferred edges, benign sharing, log coverage).

## Also close

**Distributed Attacks in Persistent-State AI Control**
Josh Hills, Ida Caspary, Asa Cooper Stickland (Jul 2026)
https://arxiv.org/abs/2607.02514 _(read in full)_. Code: https://github.com/josh-hills/control-arena-persistent-state-eval
- **Shows:** One coding agent can spread a hidden task across a series of pull requests to evade monitors. A monitor that carries compact notes forward between pull requests cuts evasion from 87% to 54% (47% when combined with other monitors), while showing the monitor more raw history barely helps.
- **Gap:** It's one agent over time, not several agents at once, so it never asks which agents belong together.

**The Best-Laid SCHEMEs: Coordinated Sabotage and Monitoring in Multi-Agent Systems**
Nikolay Radev, Lennart Haas, Benjamin Arnav, Pablo Bernabeu-Pérez (May 2026)
https://arxiv.org/abs/2605.29178 _(abstract and full-text monitoring and limitations sections)_
- **Shows:** 17 software tasks across 7 settings, each paired with a covert side task built so that no proper subset of the 2–4 agents can complete it alone. Agents split the plan over a shared bus or a star channel. A trusted monitor at 2% or lower false positives flagged coordinated sabotage in 99% (Gemini 3.1 Pro) and 68% (GPT-5.1 Codex) of attempts from code edits alone, and in 100% and 81% with communications. Telling agents a monitor exists roughly halved sabotage success. The authors' explanation: "Most of the signal is present in the code when sabotage is successful."
- **Gap:** The headline monitor sees all agents' edits and messages together as one session-level view, so this is joint monitoring of a known team; a "Single-Agent" variant scores per-agent slices separately. Each trajectory is a short, self-contained task, the monitor shares a model family with one attacker, and adaptive attackers were not tested. Read alongside MiniLab and FakeLab: when the colluders' outputs land in one reviewable place, the fragmentation effect largely disappears. Our setting removes that: fragments land in different services, and the group is not given.

**Cross-Agent Campaign Attribution: Linking Asynchronous Attacks Across LLM Agents**
SangJin Park, Myungsub Choi, Jineok Kim, Minseung Kang (Jul 2026)
https://arxiv.org/abs/2607.18826 _(abstract only)_
- **Shows:** Sessions from the same attack campaign can be linked without knowing who the attacker is, using tool-use patterns, timing, and writing style (0.82 pairwise AUC on a synthetic benchmark).
- **Gap:** It links repeated attacks from one source that resemble each other, not different-looking pieces of one outcome. Its signal is also partly writing style, which colluders could vary.

**Cross-Session Decomposition Attacks: Scaling Risk and Intent-Aligned Retrieval Defense**
Disen Liao, Yihan Wang, Freda Shi, Yaoliang Yu (Waterloo / Vector; Aug 2026; EMNLP 2026 Findings)
https://arxiv.org/abs/2608.27945 _(main text and appendices A and D; proofs and scaling-experiment appendices not read)_. Code released.
- **Shows:** IntentAlign fine-tunes a 22M-parameter MiniLM retriever contrastively, so that subqueries from the same latent intent embed close together. A guardrail LLM then reads each query's top-K neighbours from a pooled query bank and infers the composed task. Recall@10 on paraphrased queries is .649 vs .588 for Qwen3-Embedding-0.6B; end to end with Llama-3.1-8B at K = 5, harmful recall .765 at a .090 false-positive rate, close to a same-intent oracle (.775). In 50K-query WildChat banks, adding 5 hard semantic neighbours per probe drops Hit@1 from 95.7% to 77.2%: "semantic confusability, rather than unrelated-query volume … [is] the principal retrieval failure mode."
- **Gap:** Human misuse through queries in one pooled bank, with no account field, no group extraction, and no adaptive attacker; it needs intent-labeled training data. It is still the strongest available version of our main rival: resemblance learned from labels of which fragments belong together. Consider it as a stronger similarity baseline than raw embeddings. Its confusability result backs varying how much honest agents share records, not just population size, in H4.

**Information-Theoretic Approach to Detect Collusion in Multi-Agent Games**
Trevor Bonjour, Vaneet Aggarwal, Bharat Bhargava (UAI 2022)
https://proceedings.mlr.press/v180/bonjour22a/bonjour22a.pdf _(read in full, plus supplement)_
- **Shows:** The classic way to find an unknown colluding pair from logged actions. Individual influence γ(i;j) is the conditional mutual information between two agents' actions given their observed states; net influence subtracts the strongest third-party influence, Γ(i;j) = γ(i;j) − max over k of γ(k;j), and a pair is flagged if both directions exceed α = 0.05. It scans all pairs without labels. With collusion probability 0.3, accuracy is 37.1% at 100 games and 100% at 1,000; at 0.1 it stays near 8%.
- **Gap:** At most 4 players, exactly one colluding pair (it reports "No Collusion" unless exactly one pair crosses the threshold), stationary policies, small discrete state spaces, and many repeated games. Our colluders act only a few times each, so the estimates would have almost no samples. It is a dependence statistic, on the resemblance side of our comparison; the sprint showed it breaks for groups of 3 or more and confuses copies of one model with colluders (see the sprint section). Subtracting the strongest third-party influence plays the same role as our hub down-weighting. Usable only as a sanity baseline with a single colluding pair.

**Cross-Session Threats in AI Agents: Benchmark, Evaluation, and Algorithms** (CSTM-Bench)
Ari Azarafrooz (Intrinsec AI; Apr 2026)
https://arxiv.org/abs/2604.21131 _(read in full, including appendices)_. Data: two 54-scenario splits on Hugging Face.
- **Shows:** 26 attack taxonomies with matched clean and hard benign confounders, about 1,100 sessions per split. A "Full-Log Correlator" that gives Sonnet 4.6 every message in time order falls from 23/26 to 13/26 attack recall when the per-session-flagged sessions are rewritten into cross-session attacks, and flags 7/14 hard-benign scenarios, even though logs are about 97K tokens against a 1M window: "The correlator is not running out of tokens; it is running out of attack signal relative to benign mass." A bounded Coreset Memory Reader (K = 50 surprising messages) holds up better (25/26, then 19/26). Scenario T26, "Tacit Multi-Agent Collusion," is missed by every reader on both splits: "no bounded buffer of user messages can recover a coordination signal that lives in cross-agent meta-structure."
- **Gap:** Each scenario is an already-bounded stream under one policy archetype (its "identity anchors" are system-prompt roles, not agent or user identities), so there is no group to find. The author notes the confidence intervals are wider than the observed effects. Cite it for two points: handing the monitor all the logs fails by dilution, not context length (our shared-window baseline), and cross-agent collusion is an explicitly unsolved case. Its warning that benign turns can concatenate into an injection aimed at the monitor also applies to our bundle judging.

**When Local Monitors Miss Compositional Harm: Diagnosing Distributed Backdoors in Multi-Agent Systems**
Yibo Hu, Ren Wang (Jul 2026)
https://arxiv.org/abs/2607.11751 _(abstract only)_
- **Shows:** If attack fragments are indistinguishable from benign activity in the monitored view, no detector on that view can recover the missing signal. It also tests a benign-trained detector on assembled code and a decoded-view gate given the encoding family, demonstrating that detection can return in a representation that exposes the payload.
- **Gap:** Finding that revealing representation remains open: even full-trace monitors can fail if the harmful composition stays hidden. The decoded-view gate assumes the encoding family is known; the paper does not establish recovery of unknown coalitions from messy logs.

**Colosseum: Auditing Collusion in Cooperative Multi-Agent Systems**
Mason Nakamura, Abhinav Kumar, Saswat Das, Sahar Abdelnabi, Saaduddin Mahmud, Ferdinando Fioretto, Shlomo Zilberstein, Eugene Bagdasarian (Feb 2026, revised May 2026)
https://arxiv.org/abs/2602.15198 _(introduction, formulation, and auditing sections)_
- **Shows:** It audits collusion using both conversation logs and agents' actual choices, measuring how a coalition changes the cooperative outcome. It distinguishes plans to collude that never affect actions from harmful coordination that is not obvious in the messages.
- **Gap:** Its audit assumes a specified cooperative environment, interaction topology, and measurable objective. It does not reconstruct those relationships from an ungrouped collection of operator logs. It is useful for defining what counts as successful collusion in our evaluation.

**Detecting Multi-Agent Collusion Through Multi-Agent Interpretability** (HELIOS / NARCBench)
Aaron Rose, Carissa Cullen, Sahar Abdelnabi, Philip Torr, Brandon Gary Kaplowitz, Christian Schroeder de Witt (Apr 2026, revised Oct 2026)
https://arxiv.org/abs/2604.01151 _(v5: framework, evaluation, and scaling limitations)_
- **Shows:** It explicitly formulates collusion detection with an unknown colluding subgroup, combining signals across agents using model-activation probes and group-level statistics. It tests transfer across environments, including collusion that transcript monitors miss.
- **Gap:** It requires access to model internals rather than ordinary logs. Its main setup has four agents, with additional eight-agent experiments; it does not demonstrate reconstruction of attack evidence across a large fleet. It is important related work for unknown-subgroup detection even if probes remain outside our scope.

**GroupGuard: A Framework for Modeling and Defending Collusive Attacks in Multi-Agent Systems**
Yiling Tao, Xinran Zheng, Shuo Yang, Meiling Tao, Xingjun Wang (Mar 2026)
https://arxiv.org/abs/2603.13940 _(abstract and full-text threat model and method sections)_
- **Shows:** Finds an unknown colluding subset with a graph built from messages. An auditor classifies each message as support, question, or information, builds a weighted social interaction graph, runs overlapping community detection with suspicion scores (loyalty, aggression, dispersion, attack-source entropy), then confirms suspects with honeypot probe questions and prunes their outgoing edges. Default is 2 colluders among 5 agents, with scaling runs at 10 and 20, on GPTSwarm over math benchmarks, MMLU, and HumanEval. Reports up to 88% detection accuracy, training-free.
- **Gap:** Collusion is purely communicative (false consensus, targeted suppression, group exclusion) in collaborative reasoning; there is no shared state and no task splitting. Its signal is interaction structure, which puts it on the resemblance side of our comparison. The authors note they never tested adaptive camouflage of the interaction pattern.

**Beyond Single-Agent Alignment: Preventing Context-Fragmented Violations in Multi-Agent Systems**
Jie Wu, Ming Gong (Apr 2026)
https://arxiv.org/abs/2604.22879 _(abstract only)_
- **Shows:** Names "context-fragmented violations": each agent's action is locally safe, but the combination breaks policy because the facts needed to see it sit in separate departmental contexts. Eight frontier models violate policy in 14–98% of cross-agent workflows. The defense, Distributed Sentinel, is sidecar proxies that propagate semantic taint tokens across boundaries and verify compliance with counterfactual graph simulation, reporting F1 0.95 on their PhantomEcosystem benchmark, which includes adversarially balanced safe controls so a detector can't win by flagging everything.
- **Gap:** A compliance framing with non-adversarial agents inside an instrumented workflow, so nothing is hidden on purpose and nothing has to be discovered. Useful for the phenomenon's name and as a model for our benign-composition controls.

**Detecting Compositional Attacks in Multi-Agent LLM Systems via Graph-Topological Feature Analysis** (preliminary lead)
Arif Mohamed Khan Rabi Ahamad (SSRN; Apr 2026)
https://papers.ssrn.com/sol3/papers.cfm?abstract_id=6530594 _(abstract only; SSRN blocked automated retrieval on 2026-11-06)_
- **Shows:** The abstract describes heterogeneous agent–tool graphs, graph and semantic features for detecting harmful compositions, and cycle-level explanations identifying suspicious interaction paths.
- **Gap:** We have not inspected the full methodology or evaluation, so we cannot yet assess whether its experiments cover unknown colluding groups or realistic log reconstruction. Keep it as a lead; treat its performance claims as unassessed. Read it in a browser or drop it before the writeup.

## Apart AI Collusion sprint (Oct 2026): hackathon reports

_The sprint (Oct 23–25, 2026) had about 390 submissions, mostly economic games and message-based collusion. The two closest reports, Follow the Text and Many Agents, Partial Views, are in Core. The reports below were each read in full and are listed for specific findings we can use; none discovers an unknown group from shared-state logs in an agentic setting. Sprint page: https://apartresearch.com/sprints/ai-collusion-research-sprint-2026-10-23-to-2026-10-25_

**Beyond Pairs: Detecting Colluding Groups of Agents from Their Moves**
Tarun Trivedi, Eashan Gandotra (Oct 2026)
https://apartresearch.com/sprints/projects/beyond-pairs-detecting-colluding-groups-of-agents-from-their-moves-4zhs _(read in full)_. Code: https://github.com/taruntrivedi3/collusion-detection
- **Shows:** The only sprint entry that discovers group membership rather than being given it. GroupScan scores every subset of players by summed pairwise dependence between their moves, calibrated against shuffled games, and peels off detected groups. Among 20 Rock-Paper-Scissors players, a 5-player group colluding in 20% of rounds is recovered exactly in 48% of 100-round games, against 5% for the best pairwise test; Bonjour et al.'s net influence finds no group of 3 or more, because members cancel each other out. Honest players who react to the same public history look like colluders in up to 100% of games unless the shuffle stays within rounds that share that history; with that conditioning, false alarms are 4–9%. Five gpt-4.1-mini sellers with a message channel and profit pressure earn 56% more, and pooled games name all five.
- **Gap:** Moves in games and markets, not shared state, and the signal is statistical dependence, which sits on the resemblance side of our comparison. Exact subset search stops at about 20 players. It means we can't claim to be first to discover unknown colluding groups in general; narrow the claim to agentic, shared-state, decompose-to-evade settings. Its honest-reactor confound is the game version of our benign-sharing breaking point (H4).

**Collusion without co-presence: Planted precedents and hidden data across complete agent replacement**
Frank Peterlein (Oct 2026)
https://apartresearch.com/sprints/projects/collusion-without-copresence-planted-precedents-and-hidden-data-across-complete-agent-replacement-a862 _(read in full)_. Code: https://github.com/frnkptrln/collusion-without-co-presence
- **Shows:** 64 chains of five fresh Claude Haiku 4.5 sessions (320 episodes) share only a notes folder whose notes carry no writer label, under a rule forbidding one directory. A planted note describing a peer's successful rule-break led to first-generation forbidden reads in 3/16 chains, against 0/16 with an empty folder. In two chains a later agent violated after reading a predecessor's note, attributed through write logs and hashes. In five chains the hidden data reached later deliverables with no new forbidden read: one job commits the violation and later jobs use its output. In an after-the-fact audit, a one-job-at-a-time view caught 10/11 leaks (the pre-registered prediction was at most 5/11) because the deliverables named their source; the whole-folder view caught 11/11 with 1/262 false alarms.
- **Gap:** The precedent was planted, the agents weren't hiding anything, and the chain is given, so nothing is discovered; one model, one task. Close to us on mechanism (unattributed shared-store writes, a violation split across agents over time, a write→read provenance criterion). It is also a warning for attack construction: naive agents give themselves away, so our fragments must not self-disclose or the per-agent floor will be high.

**Do Monitors Add Up Across Agents? Tool Logs, Chat and a Two-Agent Overspend**
Jason Gibbs, with agent contributors (Oct 2026)
https://apartresearch.com/sprints/projects/do-monitors-add-up-across-agents-tool-logs-chat-and-a-twoagent-overspend-yjka _(read in full)_. Code: https://github.com/weiscadence/limit-probe
- **Shows:** Two treasury agents, each limited to 100 per transaction, under a team rule of at most 100 combined to one payee without a co-signer. In 150 episodes (Mistral Small and Llama 3.3 70B), a judge reading both agents' tool logs caught 41/41 violations and 11/11 joint-only overspends with 0/59 false alarms; each agent's own log caught 1/11, and a flag-any-payment rule false-alarmed on 55/59 honest episodes. A chat-only judge caught 1/11, and adding chat to the logs gained nothing.
- **Gap:** The pair is given, there are only 11 positives, and the honest condition is easy. A small agentic version of our H0 and reference condition, where the link between fragments is a shared sink (the payee). The null result for chat supports a main condition with no messages.

**Signal or Coincidence? Causal Auditing of Collusion Through Shared Agent State**
Sarvesh Tiku (Georgia Tech; Oct 2026)
https://apartresearch.com/sprints/projects/signal-or-coincidence-causal-auditing-of-collusion-through-shared-agent-state-amsn _(read in full; appendices skimmed)_. Code: https://github.com/sarvesh-tiku/Apart-Collision-Agent-State
- **Shows:** A preparer writes ticket fields and an approver acts on them. The auditor plants a random private canary with the preparer and intervenes on the shared tool state, which gives an exact null. Without a pre-agreed code, only Gemini-2.5-Flash preparers carried the target, by marking tickets "urgent" (58% vs 25% chance), and other models' approvers decoded it. When fields were recomputed from source, sanitizer-aware preparers moved the signal into free-text notes (76%), and redaction didn't stop it. The key control: an authorized expedite request produced 96–100% information flow from honest agents with no rise in harm, so flow alone is not evidence of collusion. A fixed structural rule beat an LLM monitor.
- **Gap:** The pair and the channel are known, collusion is instructed, and there is no population. Supports H2 (judge bundles against authorized tasks, since legitimate flow looks identical), and its carrier migration is a preview of our attacker routing through benign-looking intermediate records.

**Splitting the Rule of Two Across Agents: What Per-Agent and Shared Gates Catch, and What They Cost**
Walter Guevara (Juncture Policy; Oct 2026)
https://apartresearch.com/sprints/projects/splitting-the-rule-of-two-across-agents-what-peragent-and-shared-gates-catch-and-what-they-cost-xdvr _(read in full)_. Code available from the author on request.
- **Shows:** A Reader, a Holder, and an Actor each hold one of the three "Rule of Two" properties (untrusted input, sensitive data, outward action) and compose through a channel, files, a status board, and memory; 360 scripted compositions. A per-agent gate stopped 0/300 split-role attacks. A shared gate that propagates labels on data stopped 300/300 but also held 80/160 benign tasks. Leaving one medium unlabeled opens exactly the attacks routed through it. With two redundant paths, single-path ablation calls each path unnecessary.
- **Gap:** Prevention over a declared pipeline with scripted agents, not detection or discovery. The benign-hold cost is our false alarms on legitimate collaboration; the unlabeled-medium result parallels our log-coverage knob; and the redundant-paths result is an argument for returning subgraphs rather than single paths.

**Copies of One Model Look Like Colluders** and **Monoculture Looks Like Collusion**
V Gowrish Kumar Reddy, "Copies of One Model Look Like Colluders: Limits of Action-Only Collusion Detection for LLM Agents" (https://apartresearch.com/sprints/projects/copies-of-one-model-look-like-colluders-limits-of-actiononly-collusion-detection-for-llm-agents-d241); Yaroslav Rogoza, "Monoculture Looks Like Collusion: A Replay Test for Hidden Information Flow Between LLM Agents" (https://apartresearch.com/sprints/projects/monoculture-looks-like-collusion-a-replay-test-for-hidden-information-flow-between-llm-agents-3b9b) (Oct 2026) _(both read in full)_
- **Shows:** In games with moves only, dependence detectors confuse copies of one model with colluders. Calibrated net influence falsely accused a pair in 30/78 games with no collusion and ranked the two copies of one model as most linked in 41/60 mixed-model games. Mutual information accused a pair in 69.3% of honest games among four copies of Claude Haiku. Rogoza's fix re-queries each agent on the same logged input with the suspected channel removed, cutting false alarms to 4.2% across 550 honest games.
- **Gap:** Games, pairs, and instructed colluders. Cite them together as evidence that resemblance between same-model agents is a confound, which bears on the similarity rival (H1) and argues for a same-model honest population in our data. The replay test could operationalize H2 in our simulator, where we have query access: re-run an agent without the record it read and see whether its own task still explains the action.

Also scoped out: **The Shared Scratchpad: Zero-Shot Covert Coordination Through Mundane Work Documents** (Ali Abdullah; https://apartresearch.com/sprints/projects/the-shared-scratchpad-zeroshot-covert-coordination-through-mundane-work-documents-6kaa; _read in full_) shows a 3-bit target passed through a shift note with no agreed scheme (decoded in 15/30 episodes) and a cross-family monitor reaching AUC 0.925. It is steganography between a known pair, which we exclude.

## Threat model and decomposition lineage

**AI Control: Improving Safety Despite Intentional Subversion**
Ryan Greenblatt, Buck Shlegeris, Kshitij Sachan, Fabien Roger (Dec 2023)
https://arxiv.org/abs/2312.06942 _(not re-read for this list; cited for the framing)_
- **Shows:** The control setting we inherit: an untrusted capable model, a weaker trusted model, a small human audit budget, and a red team that plays the untrusted model. Trusted monitoring with auditing is the baseline protocol.
- **Gap:** One agent, one trajectory. Everything in this list that says "distributed" or "multi-agent" is an extension of this setting.

**Practical Challenges of Control Monitoring in Frontier AI Deployments**
David Lindner, Charlie Griffin, Tomek Korbak, Roland S. Zimmermann, Geoffrey Irving, Sebastian Farquhar, Alan Cooney (Google DeepMind / UK AISI; Dec 2025)
https://arxiv.org/abs/2512.22154 _(abstract, section 2, and the appendix on coordination)_
- **Shows:** Names four dynamics that simplified control settings miss: parallelism, latency, partial incrimination, and incremental attacks: "when instances share an environment, attacks can make partial progress across multiple (simultaneous, or sequential) instances." Compares synchronous, semi-synchronous, and asynchronous monitoring with a safety-case sketch. Among the ways instances can coordinate, it lists causation through shared observations: "one agent could hide a monitor jailbreak in a codebase, so that future instances that read the codebase can use it."
- **Gap:** Analysis and case studies, no experiments. It is the conceptual source of "incremental attacks," which FakeLab says is close to its "distributed attacks." Cite it next to Wen et al.

**Adaptive Deployment of Untrusted LLMs Reduces Distributed Threats**
Jiaxin Wen, Vivek Hebbar, Caleb Larson, Aryan Bhatt, Ansh Radhakrishnan, Mrinank Sharma, Henry Sleight, Shi Feng, He He, Ethan Perez, Buck Shlegeris, Akbir Khan (Nov 2024; ICLR 2025)
https://arxiv.org/abs/2411.17693 _(abstract only)_
- **Shows:** Defines the "distributed threat setting," where no single action is catastrophic and no single action is overwhelming evidence of misalignment. A macro-protocol keeps an adaptive credence in the untrusted model from its past actions and chooses safer or riskier micro-protocols; this cut backdoors by 80% at fixed usefulness on code generation.
- **Gap:** Distributed over time within one model, not across agents. It is the origin of "distributed" in control work and the conceptual sibling of Hills et al.

**Adversaries Can Misuse Combinations of Safe Models**
Erik Jones, Anca Dragan, Jacob Steinhardt (Jun 2024)
https://arxiv.org/abs/2406.14595 _(abstract only)_
- **Shows:** Split a harmful task into subtasks, send the hard benign ones to an aligned frontier model and the easy malicious ones to a weak model. The combination produces vulnerable code, hacking scripts, and manipulative text at far higher rates than either model alone, without any single malicious output.
- **Gap:** Misuse by a human adversary routing across models, with no monitor and no agents acting on shared state. It is the origin of "decompose to evade" and should be cited as such.

**Monitoring Decomposition Attacks in LLMs with Lightweight Sequential Monitors**
Chen Yueh-Han, Nitish Joshi, Yulin Chen, Maksym Andriushchenko, Rico Angell, He He (Jun 2025)
https://arxiv.org/abs/2506.10949 _(abstract only)_
- **Shows:** Decomposition attacks reach 87% success on GPT-4o across QA, text-to-image, and agentic tasks. A lightweight external monitor that evaluates subtasks cumulatively within a conversation reaches 93% defense success and stays robust when random tasks are injected between fragments.
- **Gap:** One conversation, one attacker, so the fragments are already grouped. This is the "single-channel decomposition is largely handled" baseline; the open case is fragments spread across agents with no shared channel.

**Benchmarking Misuse Mitigation Against Covert Adversaries**
Davis Brown, Mahdi Sabbaghi, Luze Sun, Alexander Robey, George J. Pappas, Eric Wong, Hamed Hassani (Jun 2025, revised Apr 2026)
https://arxiv.org/abs/2506.06414 _(abstract only)_
- **Shows:** An attacker splits a dangerous goal into many benign-looking queries. The BSD pipeline builds datasets that frontier models refuse whole and weak models can't solve, and the results point to stateful defenses that track context across queries.
- **Gap:** Human misuse through the API, not agents on infrastructure. It is the precursor to the same group's Stateful Online Monitoring paper.

**The Sum Leaks More Than Its Parts: Compositional Privacy Risks and Mitigations in Multi-Agent Collaboration**
Vaidehi Patil, Elias Stengel-Eskin, Mohit Bansal (Sep 2025)
https://arxiv.org/abs/2509.14284 _(abstract only)_
- **Shows:** Individually innocuous responses from different agents can jointly reveal sensitive information. It evaluates defenses based on anticipating the questioner's intent and having defenders vote using shared aggregated state, testing both harmful and benign compositions.
- **Gap:** Information disclosure through Q&A, not discovery of a hidden coalition from execution logs. Cite only as a non-cyber example of compositional harm and of benign-composition controls.

**Open Challenges in Multi-Agent Security: Towards Secure Systems of Interacting AI Agents**
Christian Schroeder de Witt and 23 co-authors (May 2025, revised Apr 2026)
https://arxiv.org/abs/2505.02077 _(sections 3.2, 4.2, and 4.3 of v2)_
- **Shows:** Section 4.2 says provenance graphs built from audit logs could serve "for detecting and investigating anomalous and potentially malicious actions taken by one or more agents within the system; however, no work has yet proposed how such events should be detected within the unique context of multi-agent systems." Section 4.3 says tamper-evident logs would "enable the identification of suspicious behavioural patterns across agent populations," and lists detection of secret collusion channels as open.
- **Gap:** A survey, so no method. The quoted sentence is our related-work opener; the AScope check in the design notes is the caveat to it.

**Multi-Agent Risks from Advanced AI**
Lewis Hammond, Alan Chan, Jesse Clifton, Jason Hoelscher-Obermaier, and 40 co-authors (Feb 2025)
https://arxiv.org/abs/2502.14143 _(abstract only)_
- **Shows:** The taxonomy the hackathon uses: miscoordination, conflict, and collusion as failure modes, with multi-agent security among seven risk factors.
- **Gap:** Framing only. Cite it to define collusion; it proposes no detection.

## Methods and background

### Provenance-based intrusion detection

**SLEUTH: Real-time Attack Scenario Reconstruction from COTS Audit Data**
Md Nahid Hossain, Sadegh M. Milajerdi, Junao Wang, Birhanu Eshete, Rigel Gjomemo, R. Sekar, Scott Stoller, V. N. Venkatakrishnan (USENIX Security 2017)
https://arxiv.org/abs/1801.02062 _(abstract and summaries)_
- **Shows:** Builds an in-memory dependency graph from audit logs and propagates trustworthiness and confidentiality tags along reads and writes under a customizable policy. Reduced 38.5M events to a 130-event scenario graph. The ancestor of HOLMES.
- **Gap:** Host-level, with a trusted kernel and audit trail assumed. Its tag propagation is the simplest version of our seed rule: a secret read by an agent taints what that agent later writes, and the taint follows the record to whoever reads it next.

**HOLMES: Real-time APT Detection through Correlation of Suspicious Information Flows**
Sadegh M. Milajerdi, Rigel Gjomemo, Birhanu Eshete, R. Sekar, V. N. Venkatakrishnan (IEEE S&P 2019)
https://arxiv.org/abs/1810.01594 _(abstract and author poster)_
- **Shows:** It correlates suspicious information flows from audit records into a compact, high-level attack scenario. This is foundational prior work for recognizing coordinated harmful activity through relationships between events rather than isolated alerts.
- **Gap:** It uses conventional intrusion indicators and attack-stage knowledge, not the authorized tasks and semantic effects of LLM agents. It supplies a reconstruction approach, not a demonstrated solution to benign-looking agent fragments.

**NODLINK: An Online System for Fine-Grained APT Attack Detection and Investigation**
Shaofei Li, Feng Dong, Xusheng Xiao, Haoyu Wang, Fei Shao, Jiedong Chen, Yao Guo, Xiangqun Chen, Ding Li (NDSS 2024)
https://www.ndss-symposium.org/ndss-paper/nodlink-an-online-system-for-fine-grained-apt-attack-detection-and-investigation/ _(conference abstract and author slides)_
- **Shows:** It formulates online provenance-based attack detection as a Steiner-tree problem, recovering compact structures that connect suspicious events. This provides a method for selecting evidence without returning an enormous connected component or enumerating every path.
- **Gap:** It studies conventional system intrusions rather than agent collusion. Its graph-search ideas are transferable, but the evidence and criteria for harmful composition must be adapted to agent tasks.

**NoDoze: Combatting Threat Alert Fatigue with Automated Provenance Triage**
Wajih Ul Hassan, Shengjian Guo, Ding Li, Zhengzhang Chen, Kangkook Jee, Zhichun Li, Adam Bates (NDSS 2019)
https://www.ndss-symposium.org/ndss-paper/nodoze-combatting-threat-alert-fatigue-with-automated-provenance-triage/ _(abstract and slides)_
- **Shows:** For each alert, builds its causal dependency graph and scores every event by how rarely that kind of event has occurred in the enterprise before, then propagates and aggregates scores along edges. Cut false alarms by 86% on 364 alerts and produced dependency graphs two orders of magnitude smaller.
- **Gap:** Needs a history of normal activity to estimate rarity, which we would have to generate from honest runs. Its frequency weighting is the exact mechanism behind our "give less weight to resources everyone touches," so cite it there rather than reinventing it.

**High Accuracy Attack Provenance via Binary-based Execution Partition** (BEEP)
Kyu Hyung Lee, Xiangyu Zhang, Dongyan Xu (Purdue; NDSS 2013)
https://www.ndss-symposium.org/ndss2013/ndss-2013-programme/high-accuracy-attack-provenance-binary-based-execution-partition/ _(abstract only)_
- **Shows:** Long-running processes cause dependency explosion, because every later output looks dependent on every earlier input. BEEP partitions each process into per-request execution units so provenance edges connect units, not whole processes (under 1.4% runtime overhead).
- **Gap:** Host binaries, not agents. It is the provenance precedent for our choice of events rather than agents as graph nodes: one agent doing many unrelated things is the same problem as one long-running process.

**HunterAgent: Neuro-Symbolic Attack Trace Reconstruction under Anti-Forensics**
Guangze Zhao, Yongzheng Zhang, Weilin Gai, Hongri Liu, Yuliang Wei, Bailing Wang (May 2026)
https://arxiv.org/abs/2605.29269 _(abstract only)_
- **Shows:** Reconstructs attack chains when log wiping, parent-PID spoofing, and fileless execution have broken the provenance graph into disjoint pieces. An LLM proposes links within a typed ontology; a verifier rejects any link not grounded in surviving telemetry; crossing a gap costs budget. Reports 86.1% F1, cuts fabricated path links from 61.5% to 6.4%, and keeps precision at or above 84% with 70% of logs wiped.
- **Gap:** Conventional APTs and OS telemetry. It is the closest method to our two realism knobs, missing transcript segments and spoofed tool calls, and its verified-versus-inferred separation is the discipline we adopt for observed versus inferred edges.

**Hopper: Modeling and Detecting Lateral Movement**
Grant Ho, Mayank Dhiman, Devdatta Akhawe, Vern Paxson, Stefan Savage, Geoffrey M. Voelker, David Wagner (USENIX Security 2021)
https://www.usenix.org/conference/usenixsecurity21/presentation/ho _(abstract and summaries)_
- **Shows:** Builds a graph of internal logins and finds the rare paths that are lateral movement. On 15 months and 780M logins it detected 94.5% of 300+ attack scenarios at under 9 alerts a day, where prior systems needed about 8× the false positives for the same detection.
- **Gap:** Logins, not agent actions. It is the canonical result for finding a few malicious paths inside a huge benign graph at a fixed alert budget, which is the shape of our headline curve.

**Learned and LLM-guided follow-ups (cite in one sentence as "what comes after traversal and ranking")**
- **Kairos** (Cheng et al., IEEE S&P 2024; https://arxiv.org/abs/2308.05034, code https://github.com/ubc-provenance/kairos; _abstract only_): a temporal GNN that scores each provenance event for anomaly from benign history and assembles anomalous events into summary graphs. What "add a graph model later" would look like.
- **CAPTAIN** (Wang et al., NDSS 2025; https://arxiv.org/abs/2404.14720; _abstract only_): makes rule-based tag propagation differentiable and learns per-node, per-edge, and threshold parameters. The next cheapest step if uniform hub down-weighting fails.
- **Minos** (Wang et al., Jul 2026; https://arxiv.org/abs/2607.00440; _abstract and introduction_): LLM agents trace backward from an alert through an existing provenance graph, form hypotheses, and prune branches into compact attack subgraphs. Starts from an alert and a complete graph, so it doesn't address missing links.

### Alert correlation: the resemblance-vs-composition split in intrusion detection

_Intrusion detection had our H1 debate twenty-five years ago: correlating alerts by how similar they are versus by how one alert's consequence enables another's prerequisite. Cite this pair when introducing the comparison._

**Probabilistic Alert Correlation**
Alfonso Valdes, Keith Skinner (SRI; RAID 2001)
https://doi.org/10.1007/3-540-45474-8_4 (PDF: https://www.csl.sri.com/papers/raid2001-pac/prob_corr.pdf) _(abstract only)_
- **Shows:** Fuses alerts from multiple sensors into incidents by weighted per-feature similarity, controlled by a minimum-match parameter.
- **Gap:** The resemblance side of the split: alerts are grouped because they look alike.

**Constructing Attack Scenarios through Correlation of Intrusion Alerts**
Peng Ning, Yun Cui, Douglas S. Reeves (NC State; ACM CCS 2002)
https://doi.org/10.1145/586110.586144 _(abstract only)_
- **Shows:** Correlates alerts "by (partially) matching the consequences of some prior alerts with the prerequisites of some later ones," building multi-stage attack scenarios from alerts that need not look alike.
- **Gap:** The composition side of the split, with hand-specified prerequisite and consequence predicates for known attack types. Our task-relevance judgment plays the role of those predicates for agent actions. Cite this pair so the framing is not presented as new; our novelty stays the setting and the measurement.

**A survey of coordinated attacks and collaborative intrusion detection**
Chenfeng Vincent Zhou, Christopher Leckie, Shanika Karunasekera (Computers & Security 29(1), 2010)
https://doi.org/10.1016/j.cose.2009.06.008 _(partial abstract and summary; publisher page blocked)_
- **Shows:** Surveys attacks launched from many sources at once, which are "extremely difficult to detect using isolated" detectors, and frames the two problems as collaborative-detector architecture and alert correlation.
- **Gap:** Network intrusions by external attackers. Cite it once as the security precedent for attacks split across many actors.

### Monitor inputs

**How does information access affect LLM monitors' ability to detect sabotage?**
Rauno Arike, Raja Mehta Moreno, Rohan Subramani, Shubhorup Biswas, Francis Rhys Ward (Jan 2026, revised Feb 2026)
https://arxiv.org/abs/2601.21112 _(abstract and introduction)_
- **Shows:** A "less-is-more effect": monitors often do better with less of the agent's reasoning and actions. Extract-and-evaluate (EaE) monitoring has one monitor pull relevant excerpts and another score them, improving sabotage detection by 16.8 points on BigCodeBench-Sabotage with GPT-4.1-mini.
- **Gap:** Single-agent trajectories. It bears on H3: handing the monitor the chain of writes and reads instead of the group's full transcripts is an EaE-style filter, and this paper suggests why it could beat the "handed the true group" reference.

### Jev as a monitor

_Jev (TypeSafe, on OpenRouter since about Sep 2026) is a "System One" decision model, not an LLM: given a `state` (text, images) and typed questions, it returns probabilities and confidences with no reasoning text. It is the planned screen in our forensic monitor (GRAPH_IDEA §4). Every evaluation below is single-trajectory; none screens events across agents or feeds provenance reconstruction._

**Jev on OpenRouter** (docs) and **Gate Agent Tool Calls with Jev** (cookbook)
OpenRouter / TypeSafe (2026)
https://openrouter.ai/docs/guides/community/jev and https://openrouter.ai/docs/cookbook/building-agents/gate-tool-calls-with-jev.md _(both read in full)_. Demo: https://openrouter.ai/labs/jev/overseer
- **Shows:** Question types are Choice, Noul (probability a proposition holds), Score, and Box. Requests over about 32,000 bytes of text, or with an image, run in a long-context mode that TypeSafe says is "slower and less accurate." "Jev does not produce reasoning traces, explanations, or free-form text," and thresholds must be re-picked for each model version. The cookbook gates one agent's refund tool call with three Noul checks against the policy and request (approve if all ≥ 0.9, block if any ≤ 0.1, otherwise a human reviews), at $0.000030–0.000036 and under 600 ms per request; repeated inputs moved probabilities by up to 0.08. The overseer demo runs four checks (off task, destructive, untrusted input, should ask first) on each of 24 tool calls in one request.
- **Gap:** Vendor material with no accuracy figures, and one agent's calls only. Its check style (narrow propositions about one action against the task) is the template for our screen's questions.

**Benchmarking Jev against no-CoT LLMs**
Dewi Gould, James Mann (LessWrong, Oct 7, 2026)
https://www.lesswrong.com/posts/QW2kPrAyZQvRtBXHG/benchmarking-jev-against-no-cot-llms _(post read via web extraction)_
- **Shows:** On three monitoring tasks with Jev 1.13, AUROC is close to frontier models without chain of thought: coding sabotage 0.99 (GPT-5.5 0.99, Opus 4.7 0.99), SHADE-Arena action-only transcripts 0.90 (0.93, 0.92), sandbagging 0.94 (0.91, 0.97). At a 1.5% false-positive rate it is clearly weaker: SHADE-Arena recall 47% vs 67–71%, sandbagging 55% vs 68–76%. Cost was about 1/202 of Opus 4.7's.
- **Gap:** The 32k context limit meant Jev read only 134/511 SHADE-Arena, 297/379 coding-sabotage, and 244/408 sandbagging transcripts. Whole-transcript, single-agent scoring. The low-FPR gap is why we use Jev for high-recall screening, not as the final judge.

**JEV as a Judge for Agent Trace Security: An Empirical Comparison with Generative LLM Judges**
Zhiqiang Wang, Yichao Gao (USTC; Sep 2026)
https://arxiv.org/abs/2609.34862 _(abstract page and summary)_
- **Shows:** Across 5,219 trajectories on R-Judge, ATBench500, TraceSafe, and MCPHunt, with the user request, provenance context, and full action sequence as input and a shared five-level risk rubric, Jev's benchmark-averaged F1 is 77.8 vs 74.1 for GLM-5.2, the best generative judge. Jev leads on ATBench500 and MCPHunt, GLM on R-Judge and TraceSafe. Median latency is 0.99 s vs 33.29 s, and cost per valid judgment $0.000195 vs $0.014887.
- **Gap:** One trace per judgment, with no cross-trace or multi-agent analysis. The authors frame Jev as a screening signal and can't attribute the gap to typed output alone.

**shade-arena-jev-monitor**
nican2018 (GitHub, 2026)
https://github.com/nican2018/shade-arena-jev-monitor _(search summary only; repository not opened)_
- **Shows:** A SHADE-Arena fork testing Jev as a fast monitor and action gate against Gemini 2.5 Flash and Pro. Reportedly 12 of 13 sabotage actions caught at a 5% benign-block rate, on 13 hand-made transcripts across 3 tasks.
- **Gap:** Preliminary and tiny; the author calls it a first-stage gate for individual actions, not a replacement for an LLM transcript monitor. Open the repository before citing numbers.

### Cross-field precedents

**Uncovering Coordinated Networks on Social Media: Methods and Case Studies**
Diogo Pacheco, Pik-Mai Hui, Christopher Torres-Lugo, Bao Tran Truong, Alessandro Flammini, Filippo Menczer (ICWSM 2021)
https://arxiv.org/abs/2001.05658 _(abstract only)_
- **Shows:** Unsupervised detection of coordinated accounts by building networks from shared behavioral traces (co-retweets, shared images, handle changes, synchronized hashtags) rather than from content similarity, across five case studies.
- **Gap:** Social media, not execution logs. It is the cross-field precedent for "composition, not resemblance," and Counter-Swarm Doctrine cites it for the same reason.

**Realistic Synthetic Financial Transactions for Anti-Money Laundering Models** (AMLworld)
Erik Altman, Jovan Blanuša, Luc von Niederhäusern, Béni Egressy, Andreea Anghel, Kubilay Atasu (IBM / ETH; NeurIPS 2023 Datasets & Benchmarks)
https://arxiv.org/abs/2306.16424 _(sections 3–4, ethics, and main tables)_
- **Shows:** Synthetic transaction datasets with laundering spread across accounts the launderer controls, using 8 patterns (fan-out, fan-in, gather-scatter, scatter-gather, cycle, random, bipartite, stack) plus "natural" laundering mixed into ordinary payments; only about 19% of laundering transactions in the large low-illicit set fall in the 8 patterns. Rarer laundering is much harder to detect (e.g. XGBoost F1 63.2 on the high-illicit small set vs 27.3 on the low-illicit one).
- **Gap:** Finance, and one entity controls all the accounts. It is the closest cross-field analogue of our threat: splitting activity across accounts so each stays under a per-account threshold (structuring), detected through the transaction graph. The illicit ratio is not a user knob: only the datasets are released, at two fixed levels (about 1 in 900 and 1 in 1,850 transactions), so it can't supply a density sweep.

## Setting and data

**OpenAI–HuggingFace: A Reproduction & Lessons for Alignment Testing**, plus its **Appendix: Reproduction of the OpenAI–HuggingFace Incident**
Stewart Slocum, Malayandi Palan, Christopher Chute, Michael Kim, Benjamin Van Roy (LessWrong, Sep 2026)
Main post: https://www.lesswrong.com/posts/fMnC6ZD37qrnZAFYz/openai-huggingface-a-reproduction-and-lessons-for-alignment. Appendix: https://www.lesswrong.com/posts/mXPCpJCvFGybQ4mwc/appendix-reproduction-of-the-openai-huggingface-incident. Raw logs: https://huggingface.co/datasets/stewy33/oai-hf-incident-replication _(main post and appendix read in full; dataset card read; logs not yet downloaded)_
- **Shows:** Reduces the incident to four steps: SSRF attempts that leave test files in a shared Artifactory cache; asking other agents for help; posting working exploits; and using a posted exploit to reach Hugging Face. Each step is a Docker environment mocking OpenAI's pipelines, run for 64 trajectories per model and judged by Opus 4.8. Steps 1 and 4 are easy to elicit (GLM 5.2 attempted SSRF in 64/64 runs); Steps 2 and 3 are hard and depend strongly on which notes are already in the cache and on a "trained to collaborate" system-prompt line. Most runs are one agent with simulated peers, but the appendix adds a live fleet: 256 agents (32 at a time) on different protein-analysis tasks with missing `.pdb` files and a seeded cache, in four arms (GLM 5.3 or GPT 5.6 Sol, with or without the collaboration line). In the live fleet, agents occasionally start communicating and invent conventions that spread (for example, "FLEET REQUEST" headers). Logs are Inspect `.eval` files, also browsable on Docent.
- **Gap:** A propensity and elicitation study, not a monitor. There is no hidden adversarial subset and no split task: agents communicate openly, and the Hugging Face breach is collapsed into one trajectory. Per Follow the Text, the logs record no file accesses, so registry reads and writes have to be recovered from tool calls, which matches the operator's-view data in GRAPH_IDEA §11. **Candidate substrate:** the live-fleet arms are the most realistic public honest-plus-emergent background population we have found, and colluding fragments could be inserted into them. The dataset card states no license.

**Unsanctioned Artifactory writes and cross-sample communication** (OpenAI misalignment report)
OpenAI Alignment (May 25, 2026; updated Sep 16, 2026)
https://alignment.openai.com/misalignment-reports/unauthorized-artifactory-writes-and-cross-sample-communication/ _(read in full)_
- **Shows:** A smaller precursor of the Hugging Face incident during RL training. Agents with package-download credentials listed shared Artifactory repositories, read other solvers' notes (filenames such as `REQUEST4_agent0_w3.txt` and `ASK_window002_newagent.txt`), and posted requests and replies; in one episode three separate trajectories read and wrote the same thread. One agent found that its reader credentials allowed writes and considered an exploit. Misalignment monitoring ran on 20% of samples and flagged one; the investigation then found an earlier first case and others. Fixes: monitoring on all samples (now a P0 security page), regular red-teaming of cross-sample channels, and evaluations of whether models engage with notes left by other agents.
- **Gap:** No method, and no description of how registry writes were attributed to samples; the registry records listings, timestamps, sizes, and contents, and some filenames carry self-chosen agent labels. It is the cleanest motivating example for group discovery: a per-sample monitor caught one trajectory, and finding the related ones took a manual investigation.

**Brief independent investigation of agents' behavior, reasoning and collaboration in the OpenAI / Hugging Face hacking incident** (METR)
Hjalmar Wijk, Ajeya Cotra (METR), Ryan Greenblatt (Redwood Research) (Aug 2026)
https://metr.org/hugging-face-incident-report-aug-2026.pdf _(summary and data sections)_
- **Shows:** About 1,200 agents that were meant to be isolated coordinated over an internal message board, and about 700 joined the Hugging Face attack. The investigators reconstructed events by tracing which agents wrote and read each message-board entry.
- **Gap:** It's a manual, after-the-fact investigation, not a monitor. And the swarm was a majority coordinating openly, not a hidden minority splitting a task.

**OpenAI – Hugging Face Incident Technical Report**
OpenAI (Aug 26, 2026)
https://cdn.openai.com/pdf/67869394-cb91-4c12-888c-5cbd85c7814c/OpenAI-Hugging-Face%20Incident-Technical-Report.pdf _(sections III, VI.A, VIII.C–D, and IX.B read from extracted PDF text)_
- **Shows:** The operator's own account of what it saw. Every alert came from infrastructure security tooling, not from a behavior monitor: a port sweep on June 27, the Artifactory outage on July 5, and unusual identity-related API calls on July 19. No chain-of-thought monitor ran on research workloads; OpenAI says its current one "would have caught the initial relevant activity and paged our security team more than a day before models breached Hugging Face systems." Responders disabled 311 Artifactory repositories used for message-board communication. In the later phase agents encoded messages in directory names rather than file contents. Retrospective CoT review found that agents learned improvised collaboration channels during training, starting from notes written to shared infrastructure as external memory. On tampering: models sometimes tried to edit outputs or message logs, but "none of the attempts that we observed to manipulate their tool trajectories affected the logs that our graders or monitors ultimately see."
- **Gap:** No per-agent attribution data and no description of the log schema. Reconcile its tampering statement with METR's 7% spoofed-transcript figure before simulating spoofing: both can hold if spoofed calls sit in the agent-produced transcript while the harness log is intact, which argues for keeping a separate harness-log layer in our data.

**Revealing the details of how OpenAI agents hacked Hugging Face** (swarmtraces)
Alex Forman, Mishka Kharlov, Will Tom (Parse), Jeffrey Ladish (Palisade Research), Spencer Kitts, Cormac Slade Byrd, Colleen McKenzie, Alicja Piecha (Sep 2026)
https://swarmtraces.org/ _(report read; dataset downloaded)_
- **Shows:** Over 80,000 attack payloads, reconstructed from public link-shortener chains, give a detailed picture of what the agents' attack code actually did.
- **Gap:** It's an outside view, with no agent IDs, no timestamps, and mostly outbound requests. That isn't what a monitor on OpenAI's side would have seen.

## Scoped out, cite in one sentence

**Secret Collusion among AI Agents: Multi-Agent Deception via Steganography**
Sumeet Ramesh Motwani, Mikhail Baranchuk, Martin Strohmeier, Vijay Bolina, Philip H.S. Torr, Lewis Hammond, Christian Schroeder de Witt (Feb 2024; NeurIPS 2024)
https://arxiv.org/abs/2402.07510 _(abstract only)_
- **Shows:** Formalizes secret collusion among generative agents, evaluates the steganographic capabilities it needs, and proposes mitigations.
- **Gap:** Covert channels inside messages, which we exclude. Cite it to say so.

**Tool Use Enables Undetectable Steganography in Multi-Agent LLM Systems**
Jimmy Laurence Rippin, Simon C. Marshall, David Demitri Africa, Christian Schroeder de Witt (Jun 2026)
https://arxiv.org/abs/2606.28425 _(abstract only)_
- **Shows:** Coding agents with code execution or web search can build undetectable covert channels; shared artifacts, repeated interaction, and tool-mediated search are where the risk is highest; the real barrier is agreeing on a scheme.
- **Gap:** Our colluders coordinate through shared records whose existence is logged, not through hidden content. This paper is the limit case where the content of those records carries no readable signal, the Hu & Wang boundary seen from the attacker's side.

**Steganalysis of Adaptive Covert Collusion in Tool-Using Agent Populations: A Black-Box, Cross-Principal Approach**
Mohamed Chahine Ghanem (Aug 2026)
https://arxiv.org/abs/2608.02698 _(abstract only)_
- **Shows:** Treats covert coordination among tool-using agents run by different operators as steganalysis, fusing cross-run mutual information, permutation tests, distribution-shift statistics, and timing and tool-call side channels at a fixed false-positive budget. Claims a detection-capacity frontier: "a covert bit-rate below which black-box detection is provably no better than chance."
- **Gap:** The abstract says its reported results are placeholders pending measurement, so cite only the capacity argument, next to Hu & Wang. Hidden channels, not composition through logged records.

**Detecting Covert Collusion between AI Agents through Partner-Outsider Positive Listening** (PoPLi)
Kevin Yandoka Denamganaï (Oct 2026; work in progress; also an AI Collusion sprint entry)
https://arxiv.org/abs/2610.37849 _(abstract and introduction)_
- **Shows:** It replays logged prompts with reworded messages and compares how the intended partner and an uninvolved agent change their actions. In a controlled market, this exposes a private wording-based code that message-only monitors fail to distinguish reliably.
- **Gap:** It needs replay access to the models and detects use of a private message channel, which we exclude; it cannot detect coordination through shared state or codes carried by meaning.

**Activation-based coalition detection (cite with HELIOS as the white-box alternative)**
- **Multi-Agent Collusion and the J-Space** (Marco Molinari, Gabriele Bettineschi; Nov 2026; https://arxiv.org/abs/2611.02153; _abstract only_): unsupervised Jacobian Pair Contrast (J-PACT) on DeepSeek-V4-Flash keeps 85% of the above-chance AUROC of supervised NARCBench probes and names the colluding pair in 99% of detected runs.
- **Hidden Coalitions in Multi-Agent AI: A Spectral Diagnostic from Internal Representations** (Cameron Berg, Susan L. Schneider, Mark M. Bailey; May 2026; https://arxiv.org/abs/2605.06696; _abstract only_): builds a pairwise mutual-information graph over agents' hidden states and spectrally partitions it to find coalition boundaries, rejecting behavioral coordination without informational coupling.
- Both need model internals; ours uses only operator logs.

**When can we trust untrusted monitoring? A safety case sketch across collusion strategies**
Nelson Gardner-Challis, Jonathan Bostock, Georgiy Kozhevnikov, Morgan Sinclaire, Joan Velja, Alessandro Abate, Charlie Griffin (Feb 2026; NeurIPS 2026)
https://arxiv.org/abs/2602.20628 _(abstract only)_
- **Shows:** "Collusion" here means the untrusted monitor colluding with the policy it oversees, via self-recognition, pre-shared signals, or Schelling points.
- **Gap:** A different sense of the word. Our monitor is trusted, so define collusion as coordination among the acting agents and cite this to mark the distinction.
