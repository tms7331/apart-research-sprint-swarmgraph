# Citations

The sources the work leans on: what each one supports, and where it's used. A sentence in `paper.typ` cites a source by its `refs.bib` key (`@kitaoka2026`). Add a row when the work uses a source, with its entry in `refs.bib`, and mark it once `paper.typ` cites it. Uncited entries don't print in the References.

The `read` column says how much of the source someone has read: `full text`, `abstract`, `catalogue` (its catalogue entry only), `secondhand` (through what other sources say of it) or `not checked`. The paper cites only sources read in full, and `bin/build-paper` refuses any other. `specs/KEY_PAPERS.md` holds the longer notes on each source.

| key | source | read | used for | where | in the paper |
|---|---|---|---|---|---|
| `kitaoka2026` | Kitaoka, Pham, Giudice and Merizian (2026), "Red-Teaming Multi-Agent Attacks for Loss-of-Control Risks" (MiniLab), arXiv:2610.24052 | full text | splitting a side task across agents drops per-agent detection from 86.8% to 6.7%; joint monitoring of the known team recovers 31-41% (`specs/KEY_PAPERS.md`, "read in full") | Introduction; the reproduction | yes |
| `mehta2026` | Mehta et al. (2026), "FragBench: Cross-Session Attacks Hidden in Benign-Looking Fragments", arXiv:2605.11029 | full text | the provenance graph of Experiment B: event nodes, data-flow, temporal and shared-resource edges, hub down-weighting, union-find chains (`specs/GRAPH_IDEA.md` §5, "FragBench check (full text, read 2026-11-06)"; `swarmgraph/scaling/graph.py`) | Experiment B | yes |
