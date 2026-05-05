# Design — mega-evolutions-v1

## Context
ADR-002 approved. Anchor-only mega, phased delivery. See sola-adversarial-review.

## Decisions

### D1 — Static JSON, not PokeAPI
`pokemon_team_builder/data/mega_evolutions.json` — 35 species, 37 forms.
Rationale: Champions-specific verification needed for abilities; zero runtime dependency;
entries with `"verified": false` warn at load time until manually confirmed in-game.

### D2 — MegaForm dataclass (additive to PokemonData)
```python
@dataclass
class MegaForm:
    form_id: str          # e.g. "charizard-mega-x"
    mega_stone: str       # PokePaste canonical e.g. "Charizardite X"
    types: list[str]
    ability: str
    stats: StatBlock
    verified: bool = True
```
`PokemonData` gets `megas: list[MegaForm] = field(default_factory=list)`.
Empty list = not mega-eligible. No changes to existing callers.

### D3 — assign_role_with_mega (sibling, not modify assign_role)
```python
def assign_role_with_mega(pokemon: PokemonData, mega: MegaForm | None) -> list[str]:
    if mega is None:
        return assign_role(pokemon)
    synthetic = replace(pokemon, base_stats=mega.stats, types=mega.types)
    return assign_role(synthetic)
```
Existing `assign_role` and all its tests: untouched.

### D4 — _assign_items mega_slot parameter
```python
def _assign_items(
    members_roles, members=None, preview_moves=None,
    mega_slot: tuple[int, str] | None = None,
) -> list[str]:
```
When `mega_slot=(idx, stone_name)`: that slot pre-fixed to stone_name, added to `used`,
rest of slots proceed normally. Mega Stone never considered for other slots (Item Clause).

### D5 — CLI flag --mega
```
ptb generate <anchor> --mega auto   # default: auto for single-form, error for X/Y without choice
ptb generate charizard --mega x
ptb generate charizard --mega y
ptb generate <anchor> --mega off    # treat as non-mega, bypass all mega logic
```
`generate_team(anchor, mega_choice="auto")` — new param with default.

### D6 — generate_team mega resolution
```python
def _resolve_mega(pokemon: PokemonData, choice: str) -> MegaForm | None:
    if choice == "off" or not pokemon.megas:
        return None
    if len(pokemon.megas) == 1:
        return pokemon.megas[0]  # auto
    # Multiple forms (Charizard, etc.)
    if choice in ("x", "y"):
        return next((m for m in pokemon.megas if m.form_id.endswith(choice)), None)
    raise TeamBuildError(
        f"{pokemon.name} has multiple Mega forms. Use --mega x or --mega y."
    )
```

### D7 — PokePaste serialization
No changes to `_format_species` — base species name is correct (Showdown convention).
Mega Stone item name comes directly from `MegaForm.mega_stone`.
`TeamMember` gets optional `mega_form: MegaForm | None = None`.

## Risks
- Unverified entries (`verified: false`) in data file — warn at runtime, user can ignore
- Manectric ability uncertain (Inte returned Lightning Rod; canonical Intimidate) — marked unverified
- Houndoom stats discrepancy between sources — marked unverified
- Mega ability legality in Champions (e.g. Shadow Tag Gengar) — needs in-game test
