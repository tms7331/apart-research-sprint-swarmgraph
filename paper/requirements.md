# Submission requirements: Swarm Alignment Hackathon (fetched 2026-11-07)

Source: the sprint page, https://apartresearch.com/sprints/swarm-alignment-2026. It was read through a summarizing fetch, not quoted from the page directly, so check the Guidelines tab, the official template it links and the submission form before submitting.

- **Dates:** Friday 2026-11-06 to Sunday 2026-11-08. Submissions close Sunday 2026-11-08, 11:59 PM AoE.
- **Report:** a PDF of at most 25 MB, using the official template linked on the Guidelines tab. An older template may come in acceptance emails.
- **Length:** "Maximum 8 pages, not counting references and appendices."
- **Abstract:** 150 to 250 words, submitted with the project title.
- **Authors:** names and affiliations are required.
- **Required appendix:** "Limitations and Dual-Use / Ethical Considerations". It states what the result does and does not establish, and any way the setup could make multi-agent operations easier to carry out or harder to detect.
- **Recommended structure:** Introduction, Related Work, Methodology, Results, Discussion, the Limitations appendix, References.
- **Not required here:** an LLM Usage Statement or a Code and Data section. `paper/checks.py` still requires both, a house rule carried over from the earlier sprint's build, and the paper keeps both.
- **Prior work:** code written before the sprint is marked as preexisting in the README and the report. The paper build itself is preexisting (`paper/README.md`).
- **Optional:** a public GitHub repo, a 3 to 5 minute video demo, slides, a project image.

How `paper/checks.py` enforces these: `PAGE_CAP = 8` pages before References, `ABSTRACT_WORDS = (150, 250)`, `MAX_BYTES = 25_000_000`, and the required sections, with Limitations as an appendix after References.
