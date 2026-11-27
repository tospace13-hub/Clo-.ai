# Loopholes roadmap board

A Miro-like board where a company lays out the direction it is heading. It is one file,
`index.html`, with no server and no build step: open it in a browser, or host it as a
static page (GitHub Pages works).

## What a company does with it

- **50 strategy cards** in four themes (Digitalisation, Sustainability, Business & Finance,
  Stakeholder Engagement) sit in the deck on the left. Click one to read it; drag it onto
  the board.
- **The board** crosses the four loops of the Loopholes main board (Design, Produce, Use,
  Information management) with the toolkit's time horizons (in place today, within 1 year,
  2–5 years, 5–10 years). Where a card lands says what the company does now and what it
  is heading for.
- **Notes** in three colours, as the manual recommends: what we do today, an idea for the
  future, a question. Each card can also carry a short note of the company's own.
- **About us** holds the toolkit's project description: offer, locations, what makes us
  different, strategic priorities, goals per horizon.
- **Summary** turns the board into plain text, horizon by horizon.
- **Save & share**: the board is saved in the browser as you work. To send it to someone,
  copy the board code, download it as a `.json` file, or copy a share link (the whole board
  is inside the link; nothing is uploaded).

## What it does not do yet

- People cannot work on one board at the same time. That needs a server.
- Cloé does not read the boards yet. The exported `.json` is the hand-over point: `items`
  with `type` (`card` or `note`), the card id, `x`/`y` and the note text.
- English only.

## Source and licence of the cards

The cards, the four loops and the time horizons come from the Loopholes Toolkit
(https://circularloopholes.net, source https://github.com/troykyo/dssloopholes.github.io)
by the Transitions project partners, licensed CC BY 4.0. The card texts were taken from
`assets/Cards V2 MASTER.csv` in that repository on 2026-11-27 and are embedded in
`index.html` as JSON (`<script id="cards-data">`). Each card has `id`, `t` (title), `c`
(theme: D, S, B or E), `d` (description), `q` (the question for practitioners) and `q2`
(the deeper question).

A board that is opened from a file, a link or pasted code is rebuilt field by field
(`sanitize` in `index.html`) and all text is shown as text, never as HTML.
