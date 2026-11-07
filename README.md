# swarmgraph

*Who should a monitor read together?* Our project for Apart Research's [Swarm Alignment Hackathon](https://apartresearch.com/sprints/swarm-alignment-2026) (2026-11-06 to 2026-11-08).

A monitor that reads one agent at a time catches a hidden harmful objective when one agent carries it out. When the objective is split across several agents, each piece looks harmless and the monitor largely misses it. A monitor handed the colluding team recovers some of these attacks, but a real defender doesn't know who the team is. That is MiniLab's fragmentation result ([Kitaoka et al., 2026](https://arxiv.org/abs/2610.24052)).

We ask how to find which agents to read together without being told: through the shared records they write and read, rather than through how similar they look. We also ask how each approach holds up as the honest population grows.

- **Step 1: reproduce the fragmentation result.** In a minimal, fully controlled setting, a per-agent monitor should catch a model-weight exfiltration done by one agent, miss it when it is split across three, and catch it again when the three are read together. **Done:** at a fixed threshold, the per-agent monitor flags all 4 solo attacks and none of the 4 split attacks, the joint monitor flags all 4 split attacks, and neither monitor raises a false alarm on the 16 honest teams. See the [report](reports/transfer_baseline/RESULTS.md); the split result is expected by construction ([`swarmgraph/transfer_baseline/README.md`](swarmgraph/transfer_baseline/README.md), "Limits").
- **Step 2: scale it.** Embed the same teams among growing numbers of honest agents, with a shared message board, and compare ways of choosing what to read together. This step is planned.

## Layout

| path | what |
|---|---|
| [`swarmgraph/transfer_baseline/`](swarmgraph/transfer_baseline/README.md) | **Step 1**, the minimal Kitaoka reproduction. Self-contained: scripted episodes, the LLM monitor and the analysis |
| `logs/transfer_baseline/` | Step 1's logs: the deterministic episodes and every judge reading (`judgments.jsonl`) |
| `reports/transfer_baseline/` | Step 1's report, computed from those logs |
| [`paper/`](paper/README.md) | the report, in Typst, and the build that fills its numbers, tables and figures from the logs. The build is preexisting (below) |
| [`specs/`](specs/) | the project idea (`GRAPH_IDEA.md`), the plan (`GRAPH_PLAN.md`) and notes on the key papers (`KEY_PAPERS.md`) |
| `tests/` | offline tests. None makes a model call |
| `swarmgraph/initial_experiments/`, the rest of `reports/`, `configs/`, `scripts/` | the first exploratory nine-cell pilot. Superseded by `transfer_baseline`, kept for the record, and used by nothing else |

## Running it

Needs Python 3.12+ and [uv](https://docs.astral.sh/uv/). Judge calls go through an existing ChatGPT-authenticated [Codex CLI](https://github.com/openai/codex) (`codex login status`) to `gpt-6.1-sol` at medium effort. No API keys are used.

```bash
uv sync
uv run pytest -q                                          # offline

uv run python -m swarmgraph.transfer_baseline generate    # 36 deterministic episodes, no model calls
uv run python -m swarmgraph.transfer_baseline judge       # 540 judge readings, resumable
uv run python -m swarmgraph.transfer_baseline report      # reports/transfer_baseline/RESULTS.md

bin/build-paper                                           # paper/build/DRAFT-paper.pdf
```

Add `--smoke` to the three `transfer_baseline` commands for a small run: one sample of every case type, 27 judge readings. It goes to the gitignored `logs/transfer_baseline_smoke/`.

## Preexisting work

The paper build is preexisting work, written before this sprint for our earlier Apart hackathon project, the AI Collusion Research Sprint (October 2026). It was ported from https://github.com/carver/apart-research-collusion-sprint-2026 at commit 5134da7. Thomas Redfern was a participant on that project. Its Typst template, `paper/apart.typ`, comes from Jason's earlier run (apart-oneshot-collusion). `paper/README.md` lists exactly which files were ported and what changed.

Everything else here was written during this sprint (first commit 2026-11-06 22:11 PST).
