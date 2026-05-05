# Tasks — mega-evolutions-v1

## T1 — mega_evolutions.json (R1)
- File: `pokemon_team_builder/data/mega_evolutions.json`
- 35 species, 37 forms (Charizard X/Y)
- Data from inte-mega-research.md (2026-05-05 session)
- Mark verified=false: Sableye, Scizor, Sharpedo, Slowbro, Steelix, Tyranitar, Manectric, Houndoom
- Test: test_mega_data_integrity

## T2 — MegaForm model + PokemonData.megas (R2)
- File: `pokemon_team_builder/domain/models.py`
- Add MegaForm dataclass
- Add megas: list[MegaForm] = field(default_factory=list) to PokemonData
- Test: test_pokemon_data_has_megas_field

## T3 — mega_loader (R1, R8)
- File: `pokemon_team_builder/data/loaders.py` (or new mega_loader.py)
- load_mega_evolutions() -> dict[str, list[MegaForm]]
- Warn stderr for verified=false entries
- Test: test_mega_loader_warns_unverified

## T4 — pokemon_lookup enrichment (R2)
- File: `pokemon_team_builder/services/pokemon_lookup.py`
- lookup() populates PokemonData.megas from mega_evolutions data
- Test: test_lookup_gengar_has_mega

## T5 — assign_role_with_mega (R3)
- File: `pokemon_team_builder/services/synergy_engine.py`
- Sibling function, assign_role untouched
- Test: test_assign_role_with_mega_garchomp
- Test: test_assign_role_with_mega_none_unchanged

## T6 — _assign_items mega_slot param (R4)
- File: `pokemon_team_builder/services/team_generator.py`
- Add mega_slot: tuple[int, str] | None = None
- Test: test_assign_items_mega_slot_pre_fixes_item

## T7 — _resolve_mega + generate_team wiring (R5)
- File: `pokemon_team_builder/services/team_generator.py`
- _resolve_mega(pokemon, choice) pure function
- generate_team(anchor, ..., mega_choice="auto") passes through
- _build_variant receives resolved MegaForm
- Test: test_resolve_mega_auto_single_form
- Test: test_resolve_mega_auto_multiform_raises
- Test: test_resolve_mega_x_charizard
- Test: test_resolve_mega_off_returns_none

## T8 — TeamMember.mega_form + replica_exporter (R7)
- File: `pokemon_team_builder/domain/models.py` + `replica_exporter.py`
- TeamMember gets mega_form: MegaForm | None = None
- _assign_item reads mega_form.mega_stone when set
- Test: test_pokepaste_mega_gengar_item
- Test: test_pokepaste_mega_species_base_form

## T9 — CLI --mega flag (R6)
- File: `pokemon_team_builder/cli.py`
- --mega with click.Choice(["auto","off","x","y"]), default="auto"
- Test: test_cli_mega_flag_passed_to_generate_team

## Acceptance criteria
- [ ] pytest tests/ -q → all pass
- [ ] Gengar anchor → Gengarite item, special_sweeper role
- [ ] Charizard --mega x → Charizardite X, Fire/Dragon role
- [ ] Charizard --mega auto → TeamBuildError with clear message
- [ ] Non-mega anchor → behavior unchanged vs v0.2.0
- [ ] PokePaste: species = base form, item = mega stone
