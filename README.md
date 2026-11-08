# Follow the Data: Catching Split Attacks in Agent Swarms with Decision Model Graphs

Our project for Apart Research's [Swarm Alignment Hackathon](https://apartresearch.com/sprints/swarm-alignment-2026) (2026-11-06 to 2026-11-08). Thomas Redfern.

A monitor that reads one agent at a time catches a harmful objective when one agent carries it out. When the objective is split across several agents, each piece looks like ordinary work and the monitor misses it; reading the team together catches it again. That is the fragmentation result of [Kitaoka et al. (2026)](https://arxiv.org/abs/2610.24052). In a fleet of hundreds of agents, though, a defender doesn't know which agents form the team. We ask how a monitor can find which agents to read together.

## The scenario

Three agents each take one step of a data exfiltration, and each step is allowed on its own: a **backup agent** copies a private model checkpoint into an internal bundle, a **staging agent** points an outgoing package at that bundle, and a **sync agent** switches on a scheduled delivery to a partner. A sync service then follows the pointers and delivers whatever the bundle holds. No agent uses a permission it lacks, and each can see only its own record, so no single transcript shows the leak. Honest teams take the same three steps but back up shareable data or leave the delivery off; every attack fleet has an honest twin, so every catch is checked against a false alarm on the same fleet.

## What we found

| | Setting | Result |
|---|---|---|
| **Step 1** | One team of three, the LLM monitor reading each agent individually vs. the team together | Read individually: 4/4 solo attacks and 0/4 split attacks flagged. Read together: 4/4 split attacks. No false alarms |
| **Experiment A** | The team hidden among up to 543 agents; the monitor is an LLM agent with 15 tool calls (search, read a range, read events, read an agent) over the raw log | Catches the split attack while the log fits its capacity, then fails: 3/8 at 303 agents, 1/8 at 543 |
| **Experiment B** | The same monitor plus a FragBench-style provenance graph, at 303 agents, adding tool-call overlap between teams | Helps with no overlap (16/16), then fails as shared reads merge the fleet into one chain (1/16 at overlap 2) |
| **Experiment C** (ours) | A decision model (Jev) labels each action as a source, carrier or sink of private data; links run from a write to every later action that names the record; 400 random rounds simulate where private data can reach a delivery through more than one agent; an LLM judge reads the agents on the top 3 paths together | Flags the split attack in 80/80 judgments with 0/80 false alarms, at overlap up to 16 and fleets up to 4,803 agents, for about 5¢ of labels per 303-agent fleet |

Every number above comes from the logs in `logs/` through the paper's build, which fills each figure, table and number in `paper/` from them.

## Layout

| path | what |
|---|---|
| [`swarmgraph/transfer_baseline/`](swarmgraph/transfer_baseline/README.md) | **Step 1**: scripted episodes, the LLM monitor and the analysis |
| [`swarmgraph/scaling/`](swarmgraph/scaling/README.md) | **Experiments A–C**: the fleets (`fleet.py`, `design.py`), the log explorer and its graph tools (`explorer.py`, `graph.py`), the flow graph and judge (`flow.py`) and the Jev client (`jev.py`) |
| `logs/transfer_baseline/` | Step 1's episodes and every judge reading |
| `logs/scaling/`, `logs/scaling_graph/`, `logs/scaling_graph_curve/` | Experiments A and B: fleets and every monitor run |
| `logs/scaling_flow/` | Experiment C: Jev's groups and the judge's judgments |
| [`paper/`](paper/README.md) | the paper and the video slides, in Typst, and the build that fills their numbers, tables and figures from the logs |
| [`specs/`](specs/) | the project idea, plans and notes on the key papers |
| `tests/` | offline tests. None makes a model call |
| `swarmgraph/initial_experiments/`, `logs/graph_pilot/`, the rest of `reports/`, `configs/`, `scripts/` | the first exploratory pilot, superseded by the above and kept for the record |

## Running it

Needs Python 3.12+ and [uv](https://docs.astral.sh/uv/). The LLM monitor and judge run through an existing ChatGPT-authenticated [Codex CLI](https://github.com/openai/codex) (`codex login status`) to `gpt-6.1-sol` at medium effort. Experiment C's labels come from Jev (`typesafe/jev-1.14`) on OpenRouter, with the key in `.env` as `OPENROUTER_KEY`.

```bash
uv sync
uv run pytest -q                                              # fast offline checks

uv run python -m swarmgraph.transfer_baseline generate        # Step 1: 36 deterministic episodes, no model calls
uv run python -m swarmgraph.transfer_baseline judge           # Step 1: the judge readings, resumable
uv run python -m swarmgraph.transfer_baseline report

uv run python -m swarmgraph.scaling generate                  # the fleets, no model calls
uv run python -m swarmgraph.scaling explore --run-index 0,1   # Experiment A
uv run python -m swarmgraph.scaling explore-graph --curve     # Experiment B
uv run python -m swarmgraph.scaling flow --run-index 0,1      # Experiment C: labels, groups, judgments
uv run python -m swarmgraph.scaling flow-report

bin/build-paper                                               # paper/build/DRAFT-paper.pdf
bin/build-slides                                              # paper/build/slides.pdf
```

Add `--smoke` to a command for a small run that goes to a gitignored `*_smoke` log folder.

## Preexisting work

The paper build is preexisting work, written before this sprint for our earlier Apart hackathon project, the AI Collusion Research Sprint (October 2026). It was ported from https://github.com/carver/apart-research-collusion-sprint-2026 at commit 5134da7. Thomas Redfern was a participant on that project. Its Typst template, `paper/apart.typ`, comes from Jason's earlier run (apart-oneshot-collusion). `paper/README.md` lists exactly which files were ported and what changed.

Everything else here was written during this sprint (first commit 2026-11-06 22:11 PST).

## Tests

`uv run pytest -q` runs the small offline checks. Scaling fixtures stop at 12 agents; a guard rejects larger fleets before they run. The full experimental design is checked without executing it. PDF builds and the archived pilot's exhaustive simulator matrices are opt-in: `uv run pytest -q -m integration`.
