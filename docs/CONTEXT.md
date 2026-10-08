# Context pack — facts already established (do not re-research)

Last verified: 2026-10-08. Each section says which sprint needs it.

## A. What TOS13 is (all sprints, skim once)

- **TOS13 — Textile Opportunity Space 13** (https://space13.to). A digital-physical fieldlab
  at the Textile Campus Tilburg, led by TU/e, part of the NewTexEco programme, funded by
  CLICKNL. 18 partner organisations. Central question: use data to create a sector-level
  digital orchestration layer for Dutch textile SMEs.
- Three work packages: **01 Encode / Connect** (orchestration platform that connects partners
  through TELL, matches SME questions to knowledge and capacity — *Cloé lives here*),
  02 Distill / Make (Hollanders, Vlisco, Vodde, TextielLab, Saxion), 03 Elevate / Retain
  value (ValueSort.ai, United Repair Centre, TexPlus, NXP, Saxion, ArtEZ, VNYX).
- Lineage: **WoTO** (BYBORRE's showroom) → **NewTexEco** (national network; TELL
  infrastructure) → **TOS13** (fieldlab).
- Partners (from `_data/partners.yml` on the site): TU/e, HvA, Saxion, ArtEZ, TextielMuseum
  & TextielLab Tilburg, TextielCampus Tilburg, Vlisco, EnhanceThat, Vodde, Fashion Tech Farm,
  Modint, Hollanders Printing Solutions, NewTexEco, ValueSort.ai, Stichting TexPlus, United
  Repair Centre, VNYX, NXP Semiconductors. Funder: CLICKNL.
- Contact: hello@space13.to, privacy@space13.to.
- Website repo: `tospace13-hub/tos13website` (Jekyll). Cloned read-only at
  `/home/user/tospace13-hub/tos13website` in the session that wrote this; re-clone if needed.
- Site statements that bind Cloé: the **AI statement** (`ai.md`) says no AI talks to you on
  the site today and "when a system built in the fieldlab interacts with people or
  generates content, we say so". The **privacy statement** (`privacy.md`) says join-form
  answers are used "to answer your request and involve you in the fieldlab", newsletter only
  with the tick, name/email/role never shared with NewTexEco. Both must be updated before Cloé
  messages anyone (Sprint 7).

## B. WoTO and Chloe (Sprint 0 persona, Sprint 4 composing)

- **WoTO = Window of Textile Opportunities**, launched by BYBORRE on 28 Oct 2021 at
  Naritaweg 70, Amsterdam: a physical walk-through of the textile supply chain, each stage
  (needle makers, machine makers, yarn suppliers, finishing) with its own space, plus
  BYBORRE Create workstations, panels, workshops.
- Launch consortium named in the press release (news.byborre.com, tag "woto"): machine
  makers **MEC by Santoni**, **Mayer & Cie**; material suppliers **Südwolle Group**,
  **XINAO**, **Nylstar (Hydrogen Technologies)**, **Sorona**, **Indorama Ventures / Sinterama**,
  **Trevira**; founding partner **Avery Dennison**; exhibitors **The Woolmark Company**,
  **Parley for the Oceans**; universities FIT, Parsons, AMFI, Saxion, London College of
  Fashion. Borre Akkersdijk is BYBORRE's co-founder.
- **Chloe** is the person who brought these companies together. The AI is **Cloé**, named
  after and modelled on her (the repo is "Cloé.ai"; GitHub turned the é into `-`, hence
  `Clo-.ai`). Spelling: *Chloe* for the human, *Cloé* for the AI, always signed
  "Cloé (AI)". Code identifiers are ASCII: package and CLI `cloe`, env vars `CLOE_*`. Her actual
  surname, role and writing samples are still to be collected (Sprint 0 open question).
- The full press-release text could not be read from the cloud session (host blocked, see
  section G). Read it on the MacBook and drop a copy into `docs/sources/woto-press-release.md`.

## C. Join form on space13.to (Sprint 1)

Backend: Google Apps Script (`_tools/join-form/Code.gs`) → first tab of the Google Sheet
"TOS13 join form responses" + notification email to hello@space13.to. Cloé reads the sheet
directly (`cloe ingest joinform`, Sheets API, read-only service account; Sprint 1) or a
CSV/XLSX export (`cloe ingest joinform <file>`). Tab `Responses` — header row checked
against the live sheet on 2026-10-08, identical to the list below. Tab `Unsubscribe` —
`submitted_at, email, responses_updated`. Columns of `Responses`, in order:

```
submitted_at, name, email, role,
trade_name, website, city, postcode, kvk, employees, year_start,
tier, tier_other, category, tags, outside_nl, on_tell,
interests, dpp_data, question,
consent_privacy, consent_newsletter,
tell_match, team_notes
```

- Multi-value fields are joined with `"; "`. `kvk`, `tell_match`, `team_notes` are filled by
  the team, never by the form. Cells starting with `= + - @` are stored with a leading `'`.
- `tier` values (TELL's own list): Fiber producer | Yarn & Textile producer (semi-finished
  products) | Garment production (finished product) | Wholesale | Retail | Brand | Collection
  & sorting of used textiles | Repair & Re-manufacturing | Recycling | Research & network
  organization | Other.
- `category`: Fashion | Home | Other. `outside_nl`: Yes | No. `on_tell`: Yes | No | Don't know.
- `interests`: Becoming an associate partner | Bringing a case from my organisation |
  Visiting the fieldlab | Something else. `dpp_data`: Not yet | Partly | Yes.
- `consent_privacy` = "Yes" (required; "stores my answers to follow up on this request").
  `consent_newsletter` = "Yes" or empty; the unsubscribe form sets it to "No". **This is the
  consent ledger's seed.** No SMS consent exists on the form yet — phone numbers are not
  even collected. Cloé may only SMS people who gave a number and said yes (Sprint 5 policy).

## D. TELL — tell.newtexeco.nl (Sprint 1, Sprint 3)

- Textile Ecosystem Living Lab, NewTexEco's map of ~11,000 Dutch TCLF companies from a
  Modint-KvK 2021 dataset. Built by Francesco Sollitto and Troy Nachtigall (AMFI/HvA).
  Code: `r4nd0m4gent/TELL_NTE` (public; cloned read-only at
  `/home/user/r4nd0m4gent/tell_nte` in the session that wrote this). Dash + Flask, MySQL on
  DigitalOcean, Excel fallback `data/companies.xlsx`.
- DB env (`db/mysql/.env`): `DB_USER DB_PASSWORD DB_HOST DB_NAME DB_PORT=25060 DB_CA_CERT`,
  `mysql+pymysql://…`, SSL required. Ask the TELL team for read-only credentials; never
  commit them.
- Tables: `organizations` (id, trade_name, city, postcode, status, website, employees,
  surface, year_start, legal_form, main_activity, new_main, activity_2, activity_3),
  `tags` (id, tags, category, tier, tier_original), `tags_scraped` (id, trade_name, website,
  tags_old, tags_new — curated tags + scraped keywords/bigrams), `company_class` (id,
  company_class: SME / Multinational / Frontrunner / Unclassified), `geographies` (city,
  region, latitude, longitude), `affiliations` (org_id + one flag column per consortium:
  `newtexeco2026`, `newtexeco2023`), `scraping17092026` (website, `Website emails`,
  `Website languages`, `English keywords`, `English bigrams` — the TELL scraper's output,
  emails separated by `"; "`).
- Dashboard export (no auth): `https://tell.newtexeco.nl/dashboard/export/companies.xlsx?f=<b64 json>`
  → columns Company, City, Region, Website, Employees, Surface (m2), Founded, Legal form,
  Status, Product category, Supply chain tier, Company class, Email contacts, Keywords.
  Empty `f` exports everything. Prefer this export over DB access for v1.
- Contribution form at `/contribute/` writes `additions`, `edits`, `comments` tables — Cloé
  can propose edits there instead of writing to TELL directly.
- Identity key for matching Cloé ↔ TELL: normalised website domain, then trade_name + city.

## E. Research library sources (Sprint 2)

- **m-dpp.nl/nl_funding_network.html** — the M-DPP project's page listing EU-funded textile
  projects with Dutch involvement (space13.to cites "€700M+ EU research funding … over the
  past 10 years"). M-DPP (Molecular Digital Physical Product Passport) is NWO/SIA-funded,
  HvA-led, partners incl. BYBORRE, Dutch Circular Textile Valley, Knitwear Lab. Page
  structure not yet seen (host blocked from the cloud — section G). First job of Sprint 2
  on the MacBook: save the page to `tests/fixtures/funding/nl_funding_network.html` and
  describe its structure in STATE.md.
- Expect project entries to resolve to **CORDIS** (`https://cordis.europa.eu/project/id/<id>`;
  results/deliverables under `/project/id/<id>/results`; CORDIS also has a JSON API and
  bulk datasets). Other likely sources: project websites, Zenodo, OpenAIRE.
- Textile/DPP context the library will be asked about: ESPR Digital Product Passport (EU DPP
  registry live since July 2026, textile delegated act expected 2027), EPR/UPV textiles NL,
  CIRPASS-2 deliverables, JRC textile DPP data points study (May 2026).

## F. Operational surfaces (Sprint 5, Sprint 6)

- **MacBook Pro server**: runs Claude Code under the team's Claude Max subscription. Used
  for work orders that need a person nearby or a logged-in browser (LinkedIn, blocked hosts,
  reading the WoTO press release). Cloud sessions execute sprints; the MacBook executes
  `docs/workorders/`.
- Runtime API calls from Cloé (research, summaries, drafting) need an `ANTHROPIC_API_KEY`
  — separate from Max. Every LLM job in Cloé must also be runnable as a work order so a
  Max session can do it instead (sprint.md → "Two engines, one contract").
- Slack workspace channels: #ai-log (AI session updates), #ai, #wp1 (Encode), #coordination,
  #core-partners (private), #associate-partners, #communications.

## G. Hosts blocked from cloud sessions (network policy)

`m-dpp.nl`, `news.byborre.com`, `thenextcartel.com`, `www.byborre.com`, `space13.to`,
`www.space13.to` returned "blocked by the network egress proxy" (re-tested 2026-10-08).
The team has asked for them to be allowed. For space13.to, the site's source is the
`tospace13-hub/tos13website` repo on GitHub, which is reachable — read that instead of the
live site. Either add them under *Allowed domains* in the
environment settings (https://code.claude.com/docs/en/cloud-environments#network-access) or
fetch them on the MacBook and commit the HTML into `tests/fixtures/`. `pypi.org` and
GitHub work.
