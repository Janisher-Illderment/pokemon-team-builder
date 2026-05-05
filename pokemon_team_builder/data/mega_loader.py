from __future__ import annotations

import json
import sys
from functools import lru_cache
from pathlib import Path

from pokemon_team_builder.config import DATA_DIR
from pokemon_team_builder.domain.models import MegaForm


MEGA_EVOLUTIONS_FILE: Path = DATA_DIR / "mega_evolutions.json"


@lru_cache(maxsize=1)
def load_mega_evolutions() -> dict[str, list[MegaForm]]:
    """Load mega-evolution data, keyed by lowercase species name.

    Returns ``{species_name: [MegaForm, ...]}``. Species with two megas
    (Charizard X/Y) yield two ``MegaForm`` entries distinguished by
    ``form_id`` (``charizard-mega-x`` / ``charizard-mega-y``).

    On first load any entry whose ``verified`` flag is ``False`` triggers
    a single warning to stderr listing the affected species — they are
    still returned, the warning is informational so a downstream caller
    can decide whether to surface it to the user.
    """
    with open(MEGA_EVOLUTIONS_FILE, "r", encoding="utf-8") as f:
        raw = json.load(f)

    if not isinstance(raw, dict):
        raise ValueError("mega_evolutions.json: estructura raiz invalida.")

    megas_block = raw.get("megas")
    if not isinstance(megas_block, dict):
        raise ValueError("mega_evolutions.json: campo 'megas' invalido.")

    out: dict[str, list[MegaForm]] = {}
    unverified: list[str] = []

    for species, entries in megas_block.items():
        if not isinstance(entries, list) or not entries:
            continue
        forms: list[MegaForm] = []
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            form = MegaForm.model_validate(entry)
            forms.append(form)
            if not form.verified:
                unverified.append(form.form_id)
        if forms:
            out[species.lower()] = forms

    if unverified:
        print(
            "warning: mega_evolutions.json contains unverified entries: "
            + ", ".join(sorted(unverified)),
            file=sys.stderr,
        )

    return out
