## Context

In Bo1 (closed sheet), a surprise Trick Room setter or cheese pick like Destiny Bond can win games because the opponent picks their 4 blind. In Bo3 (open sheet), the opponent sees all 6 pokémon before picking, so they can bring hard counters to cheese and avoid your Trick Room setter entirely. A strong Bo3 team needs multiple viable lead combinations so the opponent can't just "solve" your leads in Game 2.

The existing `score_team` computes `coverage (35) + roles (35) + sp (15) + items (15)`. The roles component rewards having at least one sweeper and one support — useful heuristic for Bo1 but doesn't capture "can I lead different pairs each game?" for Bo3.

The matchup analyzer needs to answer questions like "my team vs Trick Room — what do I do?" without an LLM. The approach: look up the threat's type + role + most-used moves from MetaService, check each team member's type resistances and movepool for counters, and score the team's ability to handle the threat. Then suggest targeted improvements.

## Goals / Non-Goals

**Goals:**
- `format` param on `/generate` changes scoring and generation hints for Bo3
- Lead flexibility score: count viable 4-of-6 lead pairs (both members have speed/priority advantage or role coverage advantage over the opponent's likely leads)
- Core diversity: count distinct offensive 2-pokémon cores (same-type attack partner, weather + abuser, speed control + sweeper)
- Cheese move deprioritization in Bo3: Destiny Bond, Mirror Coat, Counter, Memento get lower priority in slot 4 when `format=bo3`
- `/analyze-matchup` returns structured analysis in Spanish
- All analysis is deterministic and testable (no LLM calls)

**Non-Goals:**
- No per-matchup team regeneration (analysis only, no auto-fix)
- No full team import/validation in `/analyze-matchup` (names only, look up via pokemon_lookup)
- No support for partial teams (exactly 6 names required)
- No Bo3 series simulation

## Decisions

### D1: Lead viability heuristic
A 4-of-6 combination is "lead-viable" if at least 2 of its members together satisfy: (a) has a speed control move (Tailwind, Trick Room, Fake Out, Quick Attack) OR (b) has a priority redirect (Follow Me, Rage Powder) OR (c) has a spread attacker with STAB coverage. A team scores 1.0 if every C(6,4)=15 combination is lead-viable; typical good teams score 0.6–0.8. **Why**: simple heuristic that correlates with "I can adapt leads between games" without needing game simulation.

### D2: Core counting
A "core" is any 2-pokémon pair where one member has a role in `{physical_sweeper, special_sweeper}` and the other has a role in `{lead_support, redirect, trick_room_setter}`. Teams with ≥3 distinct cores score full core diversity points. **Why**: mirrors how VGC players describe "my offense has multiple win conditions."

### D3: Bo3 scoring formula
`coverage (30) + lead_flexibility (25) + core_diversity (15) + sp (15) + items (15)` — the roles component is redistributed into lead_flexibility + core_diversity to capture what actually matters in Bo3. Bo1 keeps the existing formula unchanged. **Why**: minimal surgery — same total 100 pts, just redistribution.

### D4: Cheese move list
`_BO3_CHEESE_MOVES = {"destiny-bond", "mirror-coat", "counter", "memento", "perish-song"}`. In `select_moves_for_role` when `format=bo3`, these moves are skipped for slot 4 and replaced by the next available role move. **Why**: in open sheet, opponents simply don't walk into Destiny Bond; it's dead weight.

### D5: Matchup threat resolution
`/analyze-matchup` resolves `threat` to a pokémon or archetype:
- If `threat` is a legal pokémon name → look it up via `pokemon_lookup.lookup()`
- If `threat` is an archetype keyword (`"trick room"`, `"weather"`, `"tailwind"`, `"redirection"`) → map to a canonical threat pokémon list
- Unknown threat → return a structured error, not a 500

### D6: Adjustment suggestion ranking
Prefer adjustments in this order: (1) move swap on existing member, (2) item swap, (3) pokémon replacement from legal pool with same role. Always suggest a specific candidate (no vague "consider a faster pokémon"). **Why**: concrete suggestions are more useful than open-ended advice.

## Risks / Trade-offs

- [Lead flexibility heuristic is approximate] → It will miss some genuine threats (e.g., a Tailwind + SR lead that doesn't fit the heuristic). Acceptable for v1 — better than no Bo3 awareness.
- [Cheese move list is incomplete] → Can be extended later; the set covers the most egregious Bo3 liabilities.
- [Matchup analysis for archetypes is hand-coded] → Archetype maps need manual maintenance when the meta shifts. Documented as a known limitation in the endpoint response.
- [pokemon_lookup makes network calls] → The analysis endpoint will be slower on cold start. Cache policy from MetaService already handles this for meta data; pokemon_lookup uses hishel cache independently.

## Open Questions

- None blocking implementation. Archetype keyword list can be expanded post-launch based on user feedback.
