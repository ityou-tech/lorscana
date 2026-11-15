"""Per-set completion buckets on the collection page are driven by rarity."""

from __future__ import annotations

import pytest

from lorscan.app.routes.collection import _build_binders, _classify_card_type
from lorscan.storage.db import Database
from lorscan.storage.models import Card, CardSet


@pytest.mark.parametrize(
    ("rarity", "expected"),
    [
        ("Common", "standard"),
        ("Uncommon", "standard"),
        ("Rare", "standard"),
        ("Super Rare", "standard"),
        ("Legendary", "standard"),
        ("Special", "standard"),
        ("Epic", "epic"),
        ("Enchanted", "enchanted"),
        ("Iconic", "iconic"),
        ("enchanted", "enchanted"),
        (None, "standard"),
        ("", "standard"),
    ],
)
def test_classify_card_type_by_rarity(rarity, expected):
    assert _classify_card_type(rarity) == expected


def _add(db: Database, number: str, rarity: str) -> None:
    db.upsert_card(
        Card(
            card_id=f"ITI-{number}",
            set_code="ITI",
            collector_number=number,
            name=f"Card {number}",
            rarity=rarity,
        )
    )


def test_enchanted_above_216_is_not_bucketed_as_iconic(db: Database):
    """ITI has 18 Enchanted cards (205-222); a fixed 216 cutoff split them 12/6."""
    db.upsert_set(CardSet(set_code="ITI", name="Into the Inklands", total_cards=204))
    _add(db, "4a", "Common")
    _add(db, "204", "Uncommon")
    _add(db, "205", "Enchanted")
    _add(db, "216", "Enchanted")
    _add(db, "217", "Enchanted")
    _add(db, "222", "Enchanted")
    _add(db, "223", "Super Rare")
    db.upsert_collection_item(card_id="ITI-4a")

    (binder,) = _build_binders(db)
    totals = {key: b["total"] for key, b in binder["buckets"].items()}

    assert totals == {"standard": 2, "epic": 0, "enchanted": 4, "iconic": 0, "promo": 1}
    assert binder["buckets"]["standard"]["owned"] == 1
    assert binder["total"] == 7
    by_number = {c["collector_number"]: c["card_type"] for p in binder["pages"] for c in p}
    assert by_number["217"] == "enchanted"
    assert by_number["223"] == "promo"


def test_regular_rarity_past_204_but_before_special_tiers_stays_standard(db: Database):
    """AOV's base set runs to #207; only regular cards after the special tiers are promos."""
    db.upsert_set(CardSet(set_code="ITI", name="Into the Inklands", total_cards=207))
    _add(db, "1", "Common")
    _add(db, "207", "Rare")
    _add(db, "208", "Epic")
    _add(db, "226", "Enchanted")
    _add(db, "244", "Iconic")
    _add(db, "246", "Legendary")

    (binder,) = _build_binders(db)
    by_number = {c["collector_number"]: c["card_type"] for p in binder["pages"] for c in p}

    assert by_number == {
        "1": "standard",
        "207": "standard",
        "208": "epic",
        "226": "enchanted",
        "244": "iconic",
        "246": "promo",
    }


def test_set_without_special_tiers_has_no_promos(db: Database):
    db.upsert_set(CardSet(set_code="ITI", name="Quest", total_cards=2))
    _add(db, "1", "Special")
    _add(db, "250", "Special")

    (binder,) = _build_binders(db)

    assert binder["buckets"]["standard"]["total"] == 2
    assert binder["buckets"]["promo"]["total"] == 0


def test_card_numbered_zero_is_a_promo(db: Database):
    """FAB's #0 Bruno Madrigal sits outside the numbered base set."""
    db.upsert_set(CardSet(set_code="ITI", name="Fabled", total_cards=204))
    _add(db, "0", "Super Rare")
    _add(db, "1", "Common")

    (binder,) = _build_binders(db)
    by_number = {c["collector_number"]: c["card_type"] for p in binder["pages"] for c in p}

    assert by_number == {"0": "promo", "1": "standard"}
