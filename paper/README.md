# The paper

**Preexisting work.** The build itself was written before this sprint for our earlier Apart hackathon project, the AI Collusion Research Sprint (October 2026), at https://github.com/carver/apart-research-collusion-sprint-2026 (commit 5134da7, 2026-10-26), and copied here: `__init__.py`, `__main__.py`, `build.py`, `checks.py`, `figures.py`, `git.py`, `ledger.py`, `typeset.py`, `watch.py`, `lib.typ`, `apart.typ`, `fonts/`, `data/__init__.py`, this README (since adapted), `bin/build-paper`, and every `tests/test_paper_*.py` except the transfer-baseline test. On copying, the only changes were the submission's name, this sprint's details, a `cell` argument to the ledger's `rate` and `pooled`, and the ledger key a CLI test expects to be missing. Since then, `__main__.py` has gained the `slides` command, and three of the tests are marked as integration tests. Everything else here is new for this sprint: `paper.typ`, `refs.bib`, `citations.md`, `requirements.md`, the slides (`slides.py`, `slides.typ` and `bin/build-slides`), and every file in `data/` except `__init__.py`. The report must say so too (`requirements.md`).

`paper.typ` is the sprint report, in [Typst](https://typst.app/docs/). `bin/build-paper` fills in its numbers, tables and figures from the logs, compiles it, and checks it against the sprint's rules (`requirements.md`).

```bash
bin/build-paper           # the draft: paper/build/DRAFT-paper.pdf, and paper/build/pages/page-NN.png
bin/build-paper --final   # the submission: paper/swarmgraph.pdf, only when every check passes
bin/build-paper watch     # the draft now, recompiled on each save and rebuilt on each commit (below)
```

`uv sync` installs everything it needs, the Typst compiler included. The font, Old Standard TT, is in `fonts/`.

`watch` keeps `build/DRAFT-paper.pdf` current while you write. A save of any `.typ` or `.bib` here recompiles it within a second or two, from the numbers and figures of the last full build, and prints Typst's error when it can't. A full build runs in the background each time HEAD moves, and when the text cites a key the ledger lacks, once the text has been still for five seconds (`--settle`). Open the PDF in a viewer that reloads a changed file, such as Skim or VS Code; macOS Preview doesn't.

Only one build of a tree runs at a time: a build holds `build/.lock`, and another waits for it, so a watch's builds and an agent's can't clear each other's figures. A watch says when another process's build pauses it.

## Writing

Write one sentence per line, so diffs and merges go sentence by sentence. Never type a number from the data. Cite it by its key, and the build fills it in:

| in paper.typ | renders | for |
|---|---|---|
| `#n("tb.solo.flagged")` | 4/4 | a count, or a plain value |
| `#pct("tb.solo.flagged")` | 100% | a count as a whole percent |
| `#ci("tb.example.cell")` | 100% (68–100%) | one cell's rate with its 95% Wilson interval |
| `#claim("text", (keys...), test)` | nothing, when it holds | wording that depends on the numbers |
| `#data-table("tb-table")` | a table | inside `#figure(...)`, captioned and labelled |
| `#data-figure("tb-figure", width: 100%)` | the figure | the same |
| `#data-text("tb.prompt")` | the text, verbatim | prompts in the appendix |
| `#todo[...]` | red TODO | anything still to write |

`build/numbers.md` lists every key with its value, how it was computed and the logs it came from, then each table's rows.

Point to a section with `@label` (`= Methods <sec-methods>`): it prints "Section 3", with no period of its own, so a sentence can end with it. Only sections have numbers, so `@label` on a subsection, or on an unnumbered section like Code and Data, prints its title, and `@label[the scope]` prints those words; either links to the heading (`heading-ref` in `lib.typ`).

Who ran what (which episodes, monitor views, readings) comes from the logs or the ledger, through a data source, not from a docstring: the docstring says what was built, not what ran. Before a sentence cites a result, read `specs/PAPER_NOTES.md`: a caveat that touches the number belongs in the sentence or in the limitations.

Cite a source only once someone has read it in full, and say so in `citations.md`'s `read` column. A source known by its catalogue entry, its abstract or what others say of it stays uncited; the build checks every source the paper cites.

An interval belongs to one cell: replies to one model and one prompt, so one view of one episode or fleet. A count pooled across cells, like Experiment A's catches over four layouts and two passes, has no interval, and `#ci` on it shows a red marker. Its replies come from different distributions, so a Wilson interval over them would be too narrow.

Put a `#claim` beside any sentence whose wording the data could make false: "most", "fell", "every model". The test gets each key's rate (or a plain value's value), in order:

```typst
#claim("the joint monitor flags more split attacks than the per-agent monitor", ("tb.split.joint.flagged", "tb.split.flagged"), (joint, alone) => joint > alone)
```

A draft marks a failing claim in red. `--final` refuses it.

## Adding numbers, tables and figures

Each module in `data/` registers data sources. A source is a function that fills a ledger, and `data/transfer_baseline.py` is the example:

```python
@source("tb")
def transfer_baseline(ledger: Ledger) -> None:
    data = summarize(read_jsonl(RUN / "episodes.jsonl"), read_jsonl(RUN / "judgments.jsonl"), design)
    ledger.rate("tb.x", readings, hit, how="...")  # one cell: by default rows sharing a model and a prompt
    ledger.pooled("tb.solo.flagged", teams, flagged, how="...", cell=("case_id",))  # no interval
    ledger.table("tb-table", header, rows_of_strings, how="...")
    ledger.figure("tb-figure", draw, data, how="...")  # draw(ax, data) with matplotlib
    ledger.value("tb.episodes", data["episodes"], how="scripted episodes")
```

Read the logs through the experiment's own analysis (`swarmgraph.transfer_baseline.analysis`), so the paper counts what the run's report counts. The build runs each source into its own ledger and refuses two that claim one key. It records which `.jsonl` files each source opened. A source that raises adds nothing, and its keys show as missing.

Lead a key with its experiment id (`tb.solo.flagged`). A key that describes a figure, such as a number or phrase in its caption or a sentence about what it shows, counts the same rows the figure draws: give it the figure's style or selection, so a tweak to the figure moves them together. Outside `paper.typ`, name a figure by its label or by what it shows, never by its number, which a new figure or a moved section changes (`tests/test_paper_sources.py`). For figures, load the `dataviz` skill first. Figures come out as SVG with their text left as text, set in the paper's font.

## What a build checks

On every build:

- pages before References: 8 at most, the title block included
- the abstract: 150 to 250 words
- no `#todo` markers
- every number, table, figure and text in the ledger
- every claim holds
- no call followed straight by a semicolon (`#n("key");`): Typst ends the call there and drops the `;`, so write `\;`
- no `#` before a digit (`(#39)`): Typst prints the number without the `#`, so write `\#39`
- every figure drawn under the section it's written in: a float that doesn't fit on its page moves on, past the next section's heading, and one placed at the top of its page can land above its own (a figure without a caption isn't checked)
- every figure and table referenced in the text
- every source the paper cites read in full: its row in `citations.md` says `full text` in the `read` column (a cited source with no row fails too)
- the Code and Data, LLM Usage Statement, and "Limitations and Dual-Use / Ethical Considerations" sections
- the PDF: 25 MB at most

It also warns, without refusing anything, about a sentence that cites the ledger and holds a word such as "every", "none", "most", "nearly" or "fell" with no `#claim` later in its paragraph. Many such words are fine; the warning asks whether the wording needs a claim.

A draft lists what fails and exits 0. `--final` also needs every link in the PDF to resolve (a network failure counts), no uncommitted changes, and every log the numbers came from pushed to `origin/main`. Only then does it write the unmarked `swarmgraph.pdf` and `swarmgraph-numbers.json`, which get committed together.

Each draft page carries a DRAFT watermark and a footer with the commit and build time, so a draft can't pass for the submission. Each build lists the ledger entries that changed since the last build that compiled, all of them in `build/changes.md`.

## Files

| file | what |
|---|---|
| `paper.typ` | the paper |
| `refs.bib` | the references (BibTeX, rendered in APA) |
| `citations.md` | the running list of sources: what each supports and where it's used |
| `lib.typ` | the functions above, and the template with the draft marks |
| `apart.typ` | the Apart template's layout. Preexisting: from Jason Carver's earlier run, updated to the live template in the AI Collusion Research Sprint project |
| `requirements.md` | this sprint's rules for the report, fetched 2026-11-07 |
| `data/` | the data sources |
| `ledger.py`, `figures.py`, `build.py`, `typeset.py`, `checks.py`, `git.py`, `__main__.py` | the build |
| `build/` | the build's output, not committed |
