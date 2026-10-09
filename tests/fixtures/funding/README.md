# Funding fixtures — HAND-WRITTEN stand-ins

Nobody in a cloud session has seen `m-dpp.nl/nl_funding_network.html` or a CORDIS page
(both hosts are blocked; see docs/CONTEXT.md §G). These files were written by hand on
2026-10-09 so `cloe scrape funding` can be built and tested. They are **not** copies of
the real pages, and the parser may not fit the real page until work order 001
(`docs/workorders/001-fetch-funding-page.md`) saves the real ones into
`tests/fixtures/funding_real/`.

Everything here is fictional: the projects, acronyms, grant ids (999000001…), companies,
documents and figures. Organisation and project-site domains are reserved `.example`
names. The CORDIS, EC and Zenodo URLs follow the public URL shapes, but the ids point to
nothing.

- `index.json`: URL → file, as `FixtureFetcher` reads it
- `nl_funding_network.html`: the project list (a table plus a card section, so the parser
  has to cope with both)
- `cordis_<id>.html` and `cordis_<id>_results.html`: two projects
- `fibreloop_site.html`: a project with no CORDIS link, only its own site
- `zenodo_9990001.html`: a publication landing page
- `deliverable_*.txt` → `deliverable_*.pdf`: regenerate the PDFs with `uv run python tests/pdfgen.py`
  (pages are separated by a form feed)
