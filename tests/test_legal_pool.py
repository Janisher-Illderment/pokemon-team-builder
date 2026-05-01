import importlib
import subprocess
import sys
from datetime import date

import pytest

from pokemon_team_builder.data.legal_pool_loader import (
    check_pool_validity,
    get_all_names,
    is_legal,
    valid_until,
)


def test_charizard_is_legal_by_name() -> None:
    assert is_legal("charizard") is True


def test_charizard_is_legal_by_id() -> None:
    assert is_legal(6) is True


def test_mewtwo_is_illegal() -> None:
    assert is_legal("mewtwo") is False


def test_iron_valiant_is_illegal() -> None:
    assert is_legal("iron-valiant") is False


def test_other_paradox_pokemon_are_illegal() -> None:
    for paradox in [
        "great-tusk",
        "flutter-mane",
        "roaring-moon",
        "iron-hands",
        "iron-bundle",
    ]:
        assert is_legal(paradox) is False, f"{paradox} should be illegal"


def test_treasures_of_ruin_are_illegal() -> None:
    for ruin in ["wo-chien", "chien-pao", "ting-lu", "chi-yu"]:
        assert is_legal(ruin) is False, f"{ruin} should be illegal"


def test_box_legendaries_are_illegal() -> None:
    for legendary in ["koraidon", "miraidon", "calyrex", "zacian", "zamazenta"]:
        assert is_legal(legendary) is False, f"{legendary} should be illegal"


def test_valid_until_returns_date() -> None:
    expiry = valid_until()
    assert isinstance(expiry, date)
    assert expiry.year == 2026
    assert expiry.month == 6
    assert expiry.day == 17


def test_get_all_names_is_list_of_strings() -> None:
    names = get_all_names()
    assert isinstance(names, list)
    assert len(names) > 100
    assert all(isinstance(n, str) for n in names)
    assert "charizard" in names


def test_is_legal_case_insensitive() -> None:
    assert is_legal("Charizard") is True
    assert is_legal("CHARIZARD") is True
    assert is_legal("  charizard  ") is True


def test_is_legal_with_invalid_type_returns_false() -> None:
    assert is_legal(None) is False  # type: ignore[arg-type]
    assert is_legal(True) is False  # bool guarded
    assert is_legal(False) is False


def test_unknown_pokemon_is_illegal() -> None:
    assert is_legal("not-a-real-pokemon") is False
    assert is_legal(99999) is False


def test_import_does_not_write_to_stderr() -> None:
    # Spawn a fresh interpreter so module-level side effects (if reintroduced)
    # would surface here instead of being masked by an already-cached import.
    result = subprocess.run(
        [sys.executable, "-c", "import pokemon_team_builder.data.legal_pool_loader"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert result.stderr == ""


def test_check_pool_validity_warns_when_expired(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    expiry = valid_until()

    class _FrozenDate(date):
        @classmethod
        def today(cls) -> date:
            return date(expiry.year + 1, expiry.month, expiry.day)

    monkeypatch.setattr(
        "pokemon_team_builder.data.legal_pool_loader.date", _FrozenDate
    )
    # Re-import Console-bound module attribute through importlib to ensure the
    # patched `date` is visible (loader imports `date` at module top).
    importlib.import_module("pokemon_team_builder.data.legal_pool_loader")

    check_pool_validity()
    captured = capsys.readouterr()
    assert "legal pool expired" in captured.err
