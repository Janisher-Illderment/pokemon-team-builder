"""Tests for the Champions M-A legal item pool.

Pins the v0.3 refactor + v0.10.1 Choice removal: WP / Throat Spray /
Rocky Helmet / Life Orb / Assault Vest / Choice Band / Choice Specs /
Choice Scarf are NOT in the M-A pool. The item map is JSON-sourced
(data_version 3) with an in-code fallback, Item Clause is enforced as a
hard rejection in _assign_items, and the backup pool is large enough to
satisfy Item Clause for a team of 6 same-role members.
"""

from __future__ import annotations

import json

import pytest

from pokemon_team_builder.config import CHAMPIONS_LEGAL_ITEMS_FILE
from pokemon_team_builder.domain.exceptions import TeamBuildError
from pokemon_team_builder.domain.models import BaseStats, PokemonData
from pokemon_team_builder.services.team_generator import (
    _BACKUP_ITEMS,
    _DEFAULT_ITEM_BY_ROLE,
    _FALLBACK_ITEM,
    _assign_items,
    _load_champions_legal_items,
)


_REMOVED_ITEMS = frozenset({
    "Weakness Policy",
    "Throat Spray",
    "Rocky Helmet",
    "Life Orb",
    "Assault Vest",
    "Choice Band",
    "Choice Specs",
    "Choice Scarf",
    "Eviolite",
    "Booster Energy",
    "Mirror Herb",
    "Loaded Dice",
    "Covert Cloak",
    "Safety Goggles",
    "Clear Amulet",
    "Light Clay",
    "Power Herb",
    # v0.10.3 (2026-05-15): Sergio's COMPLETE in-game store paste removed
    # the last cohort of "obvious VGC items" that Champions does NOT ship
    # with. Champions has a deliberately minimal 48-item economy.
    "Leftovers",
    "Focus Sash",
    "Focus Band",
    "Bright Powder",
    "Quick Claw",
    "King's Rock",
    "White Herb",
    "Sitrus Berry",
    "Lum Berry",
})


def _mk(
    name: str,
    types: list[str],
    *,
    pid: int = 1,
    hp: int = 80,
    atk: int = 100,
    def_: int = 80,
    spa: int = 100,
    spd: int = 80,
    spe: int = 90,
    moves: list[str] | None = None,
    abilities: list[str] | None = None,
) -> PokemonData:
    return PokemonData(
        id=pid,
        name=name,
        types=types,
        base_stats=BaseStats(hp=hp, atk=atk, **{"def": def_}, spa=spa, spd=spd, spe=spe),
        move_names=moves or ["protect", "tackle", "earthquake", "ice-beam"],
        abilities=abilities or ["intimidate"],
        weaknesses={},
    )


# ---------------------------------------------------------------------------
# Removed items: WP / Throat Spray / Rocky Helmet / Life Orb must not appear
# as any role default and must not leak into the backup pool.
# ---------------------------------------------------------------------------


def test_no_removed_item_in_role_defaults() -> None:
    for role, item in _DEFAULT_ITEM_BY_ROLE.items():
        assert item not in _REMOVED_ITEMS, (
            f"_DEFAULT_ITEM_BY_ROLE[{role!r}] = {item!r} is not Champions M-A legal"
        )


def test_no_removed_item_in_backup_pool() -> None:
    leaked = set(_BACKUP_ITEMS) & _REMOVED_ITEMS
    assert not leaked, f"removed items leaked into _BACKUP_ITEMS: {sorted(leaked)}"


def test_fallback_item_is_legal() -> None:
    assert _FALLBACK_ITEM not in _REMOVED_ITEMS


def test_provisional_replacements_pinned() -> None:
    # v0.10.3 (2026-05-15): role defaults after Sergio's full in-game store
    # paste — Champions has only 48 items so the defaults shifted to what
    # IS legal. Each entry MUST appear in champions_legal_items.json v5.
    assert _DEFAULT_ITEM_BY_ROLE["physical_sweeper"] == "Shell Bell"
    assert _DEFAULT_ITEM_BY_ROLE["special_sweeper"] == "Scope Lens"
    assert _DEFAULT_ITEM_BY_ROLE["physical_wall"] == "Oran Berry"


# ---------------------------------------------------------------------------
# JSON sourcing: champions_legal_items.json is the authority.
# ---------------------------------------------------------------------------


def test_legal_items_json_exists_and_loadable() -> None:
    assert CHAMPIONS_LEGAL_ITEMS_FILE.exists()
    with open(CHAMPIONS_LEGAL_ITEMS_FILE, "r", encoding="utf-8") as f:
        raw = json.load(f)
    assert raw["regulation"] == "M-A"
    assert raw["data_version"] >= 1
    assert isinstance(raw["items"], list)
    assert len(raw["items"]) > 0


def test_legal_items_json_excludes_removed_items() -> None:
    legal, _ = _load_champions_legal_items()
    for item in _REMOVED_ITEMS:
        assert item not in legal, (
            f"{item} is in champions_legal_items.json — must be removed for M-A"
        )


def test_all_role_defaults_appear_in_legal_pool() -> None:
    legal, _ = _load_champions_legal_items()
    for role, item in _DEFAULT_ITEM_BY_ROLE.items():
        assert item in legal, (
            f"role default {role!r} = {item!r} missing from champions_legal_items.json"
        )


def test_data_version_round_trips() -> None:
    legal, version = _load_champions_legal_items()
    assert version >= 1
    assert len(legal) >= 30  # backup-pool size invariant — see below


# ---------------------------------------------------------------------------
# Backup pool sized for Item Clause: 6 same-role mons must each receive a
# distinct item. The spec demands >=30 distinct items in the backup chain.
# ---------------------------------------------------------------------------


def test_backup_pool_minimum_size() -> None:
    # 6 same-role members consume 1 role default + 5 backups, but the
    # spec asks for at least 30 to leave headroom for activation filters
    # (Choice items disallowed on TR setters, type-boost items needing
    # matching type, etc).
    assert len(_BACKUP_ITEMS) >= 30, (
        f"backup pool too small ({len(_BACKUP_ITEMS)}); Item Clause headroom violated"
    )


def test_backup_pool_no_duplicates_with_defaults() -> None:
    defaults = set(_DEFAULT_ITEM_BY_ROLE.values()) | {_FALLBACK_ITEM}
    overlap = set(_BACKUP_ITEMS) & defaults
    assert not overlap, (
        f"backup pool overlaps role defaults / fallback (would force re-assignment): {sorted(overlap)}"
    )


# ---------------------------------------------------------------------------
# Item Clause hard rejection: 6 same-role mons → each gets a distinct item.
# ---------------------------------------------------------------------------


def test_assign_items_yields_six_distinct_items_for_same_role() -> None:
    members = [_mk(f"sweeper-{i}", ["normal"], pid=100 + i) for i in range(6)]
    members_roles = [["physical_sweeper"]] * 6
    items = _assign_items(members_roles, members)
    assert len(items) == 6
    assert len(set(items)) == 6, f"Item Clause violated: {items}"


def test_assign_items_raises_when_pool_too_thin(monkeypatch: pytest.MonkeyPatch) -> None:
    # Force the backup pool to be smaller than the team size so the
    # fallback chain runs out and the hard rejection triggers.
    from pokemon_team_builder.services import team_generator

    monkeypatch.setattr(team_generator, "_BACKUP_ITEMS", ("Sitrus Berry",))
    members = [_mk(f"sweeper-{i}", ["normal"], pid=200 + i) for i in range(6)]
    members_roles = [["physical_sweeper"]] * 6
    with pytest.raises(TeamBuildError) as exc_info:
        _assign_items(members_roles, members)
    assert "Item Clause" in str(exc_info.value)


def test_assign_items_filters_illegal_meta_items() -> None:
    # If MunchStats / meta_service returns a non-M-A item (e.g. Life Orb
    # or a Choice item now that Choice items have been removed),
    # _assign_items must skip it and fall back to a legal default.
    member = _mk("garchomp", ["dragon", "ground"], pid=445, atk=130, spe=102)
    items = _assign_items(
        [["physical_sweeper"]],
        [member],
        meta_items_by_member=[["Life Orb", "Choice Band", "Weakness Policy"]],
    )
    # Must NOT pick a removed item — meta or otherwise.
    assert items[0] not in _REMOVED_ITEMS, (
        f"illegal meta item leaked through: {items[0]}"
    )
    # Must pick a legal alternative — Shell Bell (physical_sweeper role default after v5).
    assert items[0] == "Shell Bell"


# ---------------------------------------------------------------------------
# Mega Stones must not appear in the legal-items JSON or in any item constant
# (managed by the mega-evolution path, not the item pool).
# ---------------------------------------------------------------------------


def test_no_mega_stone_in_legal_items() -> None:
    legal, _ = _load_champions_legal_items()
    mega_stones = [item for item in legal if item.endswith("ite") and item != "Eviolite"]
    assert mega_stones == [], (
        f"Mega Stones leaked into champions_legal_items.json: {mega_stones}"
    )


def test_no_mega_stone_in_role_defaults() -> None:
    for role, item in _DEFAULT_ITEM_BY_ROLE.items():
        assert not (item.endswith("ite") and item != "Eviolite"), (
            f"Mega Stone leaked into _DEFAULT_ITEM_BY_ROLE[{role!r}] = {item!r}"
        )
