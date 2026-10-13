# Funding fixtures

`cloe scrape funding --fixture tests/fixtures/funding` runs on this folder with no web
access: it reads the datasets from here, and `index.json` serves the saved pages.

**Real data:** the three datasets behind m-dpp.nl's research-funding network page, copied
from github.com/MDPP-ops/MDPP_Website at commit 836204b. They keep that repo's file names
and shapes, with a small sample of records:

- `cordis_textile_projects.json`: 5 real CORDIS projects (CISUTAC, PESCO-UP, AUTOLOOP,
  SORT4CIRC with Dutch partners; tExtended without one) plus one fictional record (below).
- `erasmus_textile_projects.json`: 2 real Erasmus+ projects, one with a Dutch partner and
  one without.
- `nwo_fashion_textile_filtered.json`: 2 real NWO/SIA projects. Researchers' names, ORCIDs
  and author lists were removed (Cloé keeps only organisations); only role and organisation
  are left.

**Hand-written (fictional):** nobody in a cloud session has seen a CORDIS results page or
a deliverable (cordis.europa.eu and ec.europa.eu are blocked; docs/CONTEXT.md §G). So one
fictional project tests that path end to end. KNITPASS, grant id 999000001, is marked
"fictional test record" in its title and abstract, and has these files:

- `cordis_999000001_results.html`: its results page
- `deliverable_knitpass_d2_1.txt` → `deliverable_knitpass_d2_1.pdf`: regenerate the PDF with
  `uv run python tests/pdfgen.py` (pages are separated by a form feed)
- `zenodo_9990001.html`: a publication landing page

Organisations in the fictional files are made-up "Voorbeeld" names. The EC and Zenodo URLs
follow the public URL shapes, but their ids point to nothing. Work order 001 asks the
MacBook for real results pages and a real deliverable.
