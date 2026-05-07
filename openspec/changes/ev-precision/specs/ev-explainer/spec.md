## ADDED Requirements

### Requirement: ev_explainer.explain produces specific Spanish EV rationale
`services/ev_explainer.py` SHALL expose `explain(member: TeamMember, speed_db: SpeedTierDB, meta: MetaService | None) -> str` that returns a 1–2 sentence Spanish string describing what the SP investment achieves. If `sp_distribution` is all zeros it SHALL return `""`.

#### Scenario: Speed investment note
- **WHEN** a member has `spe > 0` in their sp_distribution
- **THEN** the note names at least one pokémon beaten and one not beaten from the speed tier database, e.g. "32 Spe supera a Rillaboom (100) e Incineroar (57) — no alcanza a Flutter Mane (171)"

#### Scenario: Defensive investment note with known attacker
- **WHEN** a member has `hp > 0` or `def_ > 0` or `spd > 0` and meta data is available
- **THEN** the note names the specific attack and attacker and states the survival result, e.g. "32 HP + 32 Def aguanta el Terremoto de Landorus-T"

#### Scenario: Defensive investment note without meta data
- **WHEN** bulk EVs are present but `meta` is `None`
- **THEN** the note uses the `COMMON_ATTACKS` fallback and still names a specific move, e.g. "32 HP + 32 Def aguanta un Terremoto Tierra con alta probabilidad"

#### Scenario: No investment
- **WHEN** all SP values are 0
- **THEN** `explain()` returns `""`

### Requirement: explain prioritizes speed note over defensive note
When a member has both Spe investment and bulk investment, the speed note SHALL appear first in the returned string, with the defensive note appended as a second sentence.

#### Scenario: Mixed investment
- **WHEN** sp_distribution contains both spe and hp/def values
- **THEN** the returned string begins with the speed note and ends with the defensive note as a separate sentence
