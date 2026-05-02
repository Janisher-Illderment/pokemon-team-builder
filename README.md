# pokemon-team-builder

CLI to generate competitive **Pokémon Champions** teams — Doubles format, Regulation M-A.

Given an anchor Pokémon you love, the tool selects 5 teammates from the legal pool, scores
each variant 0–100, and exports a PokePaste ready to import into PikaChampions or ChampTeams.gg.

---

## Requirements

- Internet access on first run (PokeAPI data is cached locally after that)

## Installation

### Option A — Standalone executable (no Python needed)

Download the latest `poke-builder.exe` from the
[Releases page](https://github.com/Janisher-Illderment/pokemon-team-builder/releases)
and run it from any folder:

```
poke-builder build charizard
```

### Option B — Install from GitHub (Python 3.11+ required)

```bash
pip install git+https://github.com/Janisher-Illderment/pokemon-team-builder.git
```

That's it. The `poke-builder` command is now available globally.

### Option C — Editable install (for development)

```bash
git clone https://github.com/Janisher-Illderment/pokemon-team-builder.git
cd pokemon-team-builder
pip install -e ".[dev]"   # or: uv pip install -e ".[dev]"
```

## Quick Usage

### Build a team

```bash
poke-builder build charizard
```

Generate up to 3 team variants around Charizard, display a scored table, and print the PokePaste.

```bash
# Save to a file
poke-builder build garchomp --output team.txt

# Force overwrite if file exists
poke-builder build garchomp --output team.txt --force

# Fewer variants
poke-builder build meowscarada --variants 1

# Machine-readable JSON output
poke-builder build dragapult --json
```

### Inspect a Pokémon

```bash
poke-builder check charizard
```

Shows Pokédex ID, types, base stats, type matchups (≥2× weaknesses), and the Doubles roles
the engine would assign (sweeper, wall, lead, trick-room setter, redirect).

---

## Importing into Pokémon Champions

1. Run `poke-builder build <pokemon> --output team.txt`
2. Copy the contents of `team.txt`
3. Go to **https://pikachampions.com/** or **https://champteams.gg/**
4. Paste the text and choose **Import Replica Team**
5. Use the generated code inside the game to load the team

The export uses Showdown PokePaste format: `Level: 50`, `EVs:` (SPs × 8), no `IVs:` line,
Protect in move slot 1.

---

## Data Sources

| Source | What it provides |
|--------|-----------------|
| [PokéAPI](https://pokeapi.co/) | Base stats, types, move pool, abilities |
| [PikaChampions](https://pikachampions.com/) | Regulation M-A legal pool reference |
| Local cache | `~/.pokemon-builder/cache.db` — SQLite, 30-day TTL |

On first run the tool fetches data for every Pokémon in the legal pool (~380 entries). Subsequent
runs are fully offline.

---

## Known Limitations

- **Move pool**: sourced from PokéAPI (main series). Some moves may not be available in
  Pokémon Champions; treat generated sets as starting suggestions.
- **Legal pool**: `data/legal_pool_mA.json` was built heuristically (~380 entries). Verify against
  the official list at https://pikachampions.com/ before competitive play.
- **Mega Evolutions**: the 59 Mega forms in Champions are not yet modeled.
- **Regulation expiry**: Regulation M-A is valid until 2026-06-17. The CLI warns when the
  regulation has expired.

---

## Development

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Run the test suite
pytest

# Run with coverage
pytest --cov
```

81 tests, targeting ≥80% line coverage.

---

## License

MIT
