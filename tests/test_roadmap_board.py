"""The roadmap board (roadmap/index.html) is one static page; check what it ships."""

import json
import re
from collections import Counter
from pathlib import Path

PAGE = (Path(__file__).parent.parent / "roadmap" / "index.html").read_text(encoding="utf-8")


def _cards() -> list[dict]:
    found = re.search(r'<script type="application/json" id="cards-data">(.*?)</script>', PAGE, re.DOTALL)
    assert found
    return json.loads(found.group(1))


def test_all_fifty_loopholes_cards_are_embedded():
    cards = _cards()
    assert len(cards) == 50
    assert len({card["id"] for card in cards}) == 50
    assert Counter(card["c"] for card in cards) == {"D": 12, "S": 12, "B": 13, "E": 13}
    for card in cards:
        assert card["t"] and card["d"] and card["q"]
        assert re.fullmatch(r"[a-z0-9-]+", card["id"])


def test_example_board_uses_real_card_ids():
    ids = {card["id"] for card in _cards()}
    example = PAGE.split("function example()")[1].split("var state")[0]
    used = set(re.findall(r"\bc\('([a-z0-9-]+)'", example))
    assert used and used <= ids


def test_page_loads_no_scripts_from_elsewhere_and_credits_the_toolkit():
    assert not re.search(r"<script[^>]+src=", PAGE)
    assert "innerHTML" not in PAGE
    assert "CC BY 4.0" in PAGE and "circularloopholes.net" in PAGE
