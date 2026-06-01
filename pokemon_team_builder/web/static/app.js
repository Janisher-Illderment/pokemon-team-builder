function app() {
  return {
    anchor: '',
    variants: '3',
    format: 'bo1',
    archetype: 'balance',
    // C1: team sheet visibility. 'auto' = legacy mapping (bo3=open, bo1=closed).
    teamSheet: 'auto',
    loading: false,
    error: '',
    results: [],
    matchupThreat: '',
    matchupVariantIndex: 0,
    matchupLoading: false,
    matchupError: '',
    matchupResult: null,

    // editor state
    editState: null,   // { variantIndex, memberIndex, kind, slot, move, item, pokemon }
    editLoading: false,
    editError: '',
    legalPool: [],

    // import state
    importPaste: '',
    importLoading: false,
    importError: '',
    importedVariants: [],

    // B7 — "Valorar equipo" state. Mirrors the import plumbing: paste in a
    // textarea, POST /rate-team, render the TeamRatingOut. teamRating holds
    // the full response object (null until the first successful call).
    ratePaste: '',
    rateLoading: false,
    rateError: '',
    teamRating: null,

    // Phase 4a: per-member SP preset choice. Keyed as `${variantIdx}:${memberIdx}` → 'offensive' | 'defensive'. Default offensive.
    presetChoice: {},

    async init() {
      try {
        const r = await fetch('/legal-pool');
        if (r.ok) { const d = await r.json(); this.legalPool = d.names || []; }
      } catch {}
      // C3 light: pre-fill form from URL query params so SEO landing
      // pages (/pokemon/{slug} and /archetype/{slug}) can CTA-link here
      // with the user's intent already loaded. Supported params:
      //   ?anchor=garchomp      → fills the anchor input
      //   ?archetype=hyper_offense
      //   ?format=bo1 | bo3
      //   ?team_sheet=auto | open | closed
      //   ?auto=1               → triggers generate() once form is ready
      const params = new URLSearchParams(window.location.search);
      const validArchetypes = new Set([
        'balance', 'hyper_offense', 'hard_trick_room', 'bulky_offense',
        'weather_based', 'stall', 'perish_trap',
      ]);
      const anchorParam = params.get('anchor');
      if (anchorParam) this.anchor = anchorParam.trim().toLowerCase();
      const archParam = params.get('archetype');
      if (archParam && validArchetypes.has(archParam)) this.archetype = archParam;
      const formatParam = params.get('format');
      if (formatParam === 'bo1' || formatParam === 'bo3') this.format = formatParam;
      const sheetParam = params.get('team_sheet');
      if (sheetParam === 'auto' || sheetParam === 'open' || sheetParam === 'closed') {
        this.teamSheet = sheetParam;
      }
      if (params.get('auto') === '1' && this.anchor) {
        // Defer one tick so Alpine state is fully bound + form rendered.
        setTimeout(() => this.generate(), 50);
      }
      window.addEventListener('meta-prefill-import', (e) => {
        this.importPaste = e.detail.paste || '';
        this.importError = '';
        const el = document.getElementById('import-section');
        if (el) el.scrollIntoView({ behavior: 'smooth' });
      });
    },

    async generate() {
      this.error = '';
      this.results = [];
      this.presetChoice = {};
      this.matchupResult = null;
      this.matchupError = '';
      this.loading = true;
      try {
        const res = await fetch('/generate', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            anchor: this.anchor.trim().toLowerCase(),
            variants: parseInt(this.variants),
            format: this.format,
            archetype: this.archetype,
            team_sheet: this.teamSheet,
          }),
        });
        const data = await res.json();
        if (!res.ok) {
          this.error = data.detail ?? 'Unknown error';
        } else {
          this.results = data.variants;
        }
      } catch (e) {
        this.error = 'Network error — is the server running?';
      } finally {
        this.loading = false;
      }
    },

    // Phase 4a — UI helpers for archetype badge, SP preset toggle.
    archetypeLabel(a) {
      const map = {
        balance: 'Balance',
        hyper_offense: 'Hiperofensivo',
        hard_trick_room: 'Trick Room',
        bulky_offense: 'Bulky offense',
        weather_based: 'Weather',
        stall: 'Stall',
        perish_trap: 'Perish trap',
      };
      return map[a] || a;
    },

    hasPresets(member) {
      // v0.10.1 (2026-05-15): prefer the full preset_kits when present.
      // Fall back to the legacy SPs-only sp_presets for variants imported
      // before the kit refactor.
      const k = member && member.preset_kits;
      if (k && (k.offensive || k.defensive)) return true;
      const p = member && member.sp_presets;
      return !!(p && (p.offensive || p.defensive));
    },

    presetFor(variantIdx, memberIdx) {
      return this.presetChoice[`${variantIdx}:${memberIdx}`] || 'offensive';
    },

    setPreset(variantIdx, memberIdx, choice) {
      this.presetChoice[`${variantIdx}:${memberIdx}`] = choice;
    },

    // v0.10.1: return the kit for the selected preset — item/ability/nature/
    // moves/sp_distribution come from preset_kits, not just SPs. Falls back
    // to a synthesised kit built from the legacy member fields when the
    // backend didn't ship preset_kits (older variants).
    kitForPreset(member, presetName) {
      const kits = member && member.preset_kits;
      if (kits && kits[presetName]) return kits[presetName];
      // Legacy fallback: only SPs change, the rest mirrors the offensive
      // build.
      const legacySp = (member && member.sp_presets && member.sp_presets[presetName]) || member.sp_distribution || {};
      return {
        item: member.item,
        ability: member.ability,
        nature: member.nature,
        moves: member.moves,
        sp_distribution: legacySp,
      };
    },

    // Returns the SP grid for the selected preset; falls back to legacy sp_distribution if presets missing.
    spGridForPreset(member, presetName) {
      const kit = this.kitForPreset(member, presetName);
      const sp = kit.sp_distribution || {};
      return [
        { stat: 'HP',  key: 'hp',  val: sp.hp  || 0 },
        { stat: 'Atk', key: 'atk', val: sp.atk || 0 },
        { stat: 'Def', key: 'def', val: sp.def || 0 },
        { stat: 'SpA', key: 'spa', val: sp.spa || 0 },
        { stat: 'SpD', key: 'spd', val: sp.spd || 0 },
        { stat: 'Spe', key: 'spe', val: sp.spe || 0 },
      ].map(s => ({ ...s, active: s.val > 0 }));
    },

    capitalize(str) {
      return str.replace(/-/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
    },

    spGrid(member) {
      const sp = member.sp_distribution || {};
      return [
        { stat: 'HP',  key: 'hp',  val: sp.hp  || 0 },
        { stat: 'Atk', key: 'atk', val: sp.atk || 0 },
        { stat: 'Def', key: 'def', val: sp.def || 0 },
        { stat: 'SpA', key: 'spa', val: sp.spa || 0 },
        { stat: 'SpD', key: 'spd', val: sp.spd || 0 },
        { stat: 'Spe', key: 'spe', val: sp.spe || 0 },
      ].map(s => ({ ...s, active: s.val > 0 }));
    },

    async copy(text, event) {
      try {
        await navigator.clipboard.writeText(text);
        const btn = event.target;
        const orig = btn.textContent;
        btn.textContent = 'Copied!';
        setTimeout(() => { btn.textContent = orig; }, 1500);
      } catch {
        // clipboard blocked (non-HTTPS) — silently ignore
      }
    },

    saveTeam(variant) {
      window._savedTeams && window._savedTeams.save(variant);
    },

    async analyzeMatchup() {
      if (!this.matchupThreat.trim() || !this.results.length) return;
      this.matchupError = '';
      this.matchupResult = null;
      this.matchupLoading = true;
      const variant = this.results[this.matchupVariantIndex] || this.results[0];
      const team = variant.members.map(m => m.name);
      try {
        const res = await fetch('/analyze-matchup', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ team, threat: this.matchupThreat.trim() }),
        });
        const data = await res.json();
        if (!res.ok) {
          this.matchupError = data.detail ?? 'Error al analizar';
        } else {
          this.matchupResult = data;
        }
      } catch {
        this.matchupError = 'Error de red';
      } finally {
        this.matchupLoading = false;
      }
    },

    memberSprite(name) { return spriteUrl(name); },

    startEdit(variantIndex, memberIndex, kind) {
      const m = this.results[variantIndex].members[memberIndex];
      this.editState = {
        variantIndex,
        memberIndex,
        kind,
        slot: 0,
        move: m.moves[0] || '',
        item: m.item || '',
        pokemon: '',
      };
      this.editError = '';
    },

    cancelEdit() {
      this.editState = null;
      this.editError = '';
    },

    _buildVariantIn(variant) {
      return {
        members: variant.members.map(m => ({
          name: m.name,
          role: m.roles,
          item: m.item,
          ability: m.ability,
          nature: m.nature,
          moves: m.moves,
          sp_distribution: m.sp_distribution || {},
          mega_form_id: m.mega_form_id || null,
        })),
        score: variant.score || 0,
        format_mode: variant.format_mode || 'bo1',
      };
    },

    async submitEdit() {
      if (!this.editState) return;
      const { variantIndex, memberIndex, kind, slot, move, item, pokemon } = this.editState;
      const variant = this.results[variantIndex];

      let edit;
      if (kind === 'move_swap') {
        edit = { kind: 'move_swap', slot_index: parseInt(slot), new_move: move.trim().toLowerCase().replace(/ /g, '-') };
      } else if (kind === 'item_swap') {
        edit = { kind: 'item_swap', new_item: item.trim() };
      } else {
        edit = { kind: 'pokemon_swap', new_pokemon_name: pokemon.trim().toLowerCase().replace(/ /g, '-') };
      }

      this.editLoading = true;
      this.editError = '';
      try {
        const res = await fetch('/edit-member', {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            variant: this._buildVariantIn(variant),
            member_index: memberIndex,
            edit,
          }),
        });
        const data = await res.json();
        if (!res.ok) {
          this.editError = data.detail ?? 'Error al editar';
        } else {
          this.results[variantIndex] = data;
          this.editState = null;
        }
      } catch {
        this.editError = 'Error de red';
      } finally {
        this.editLoading = false;
      }
    },

    async importTeam() {
      if (!this.importPaste.trim()) return;
      this.importError = '';
      this.importLoading = true;
      try {
        const res = await fetch('/import', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ pokepaste: this.importPaste }),
        });
        const data = await res.json();
        if (!res.ok) {
          this.importError = data.detail ?? 'Error al importar';
        } else {
          this.importedVariants = [data];
          this.importPaste = '';
        }
      } catch {
        this.importError = 'Error de red';
      } finally {
        this.importLoading = false;
      }
    },

    // B7 — POST the pasted team to /rate-team and store the TeamRatingOut.
    // no-store on the POST so a proxy/browser never serves a stale rating
    // for the same paste after a backend deploy that changed the scoring.
    async rateTeam() {
      if (!this.ratePaste.trim()) return;
      this.rateError = '';
      this.rateLoading = true;
      this.teamRating = null;
      try {
        const res = await fetch('/rate-team', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          cache: 'no-store',
          body: JSON.stringify({ pokepaste: this.ratePaste }),
        });
        const data = await res.json();
        if (!res.ok) {
          this.rateError = data.detail ?? 'Error al valorar';
        } else {
          this.teamRating = data;
        }
      } catch {
        this.rateError = 'Error de red';
      } finally {
        this.rateLoading = false;
      }
    },

    // B7 — bucket a 0..100 score into a CSS modifier so the UI tints the
    // global note and per-mon badges by quality tier. Shared by team score
    // (float 0..100) and member score (int 1..100).
    scoreTier(score) {
      if (score >= 75) return 'high';
      if (score >= 50) return 'mid';
      return 'low';
    },
  };
}

function savedTeams() {
  const STORAGE_KEY = 'poke-builder-presets';
  const MAX_PRESETS = 20;
  const COLOR_PALETTE = ['#e74c3c','#3498db','#2ecc71','#f39c12','#9b59b6','#1abc9c'];

  return {
    presets: [],
    showPanel: false,
    saveWarning: '',
    showChangelog: false,
    changelog: [],

    async init() {
      window._savedTeams = this;
      const raw = localStorage.getItem(STORAGE_KEY);
      try { this.presets = raw ? JSON.parse(raw) : []; } catch { this.presets = []; }
      try {
        // no-store: el changelog cambia con cada release; evitar que el
        // navegador sirva una versión cacheada tras un deploy.
        const r = await fetch('/changelog.json', { cache: 'no-store' });
        if (r.ok) this.changelog = await r.json();
      } catch {}
    },

    _persist() {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(this.presets));
    },

    save(variant) {
      if (this.presets.length >= MAX_PRESETS) {
        this.saveWarning = 'Máximo 20 equipos guardados';
        setTimeout(() => { this.saveWarning = ''; }, 3000);
        return;
      }
      this.saveWarning = '';
      const n = this.presets.length + 1;
      this.presets.push({
        id: Date.now(),
        name: `Equipo ${n}`,
        color: COLOR_PALETTE[(n - 1) % COLOR_PALETTE.length],
        score: variant.score,
        pokepaste: variant.pokepaste,
        members: variant.members.map(m => m.name),
        timestamp: new Date().toLocaleDateString('es-ES'),
      });
      this._persist();
    },

    remove(id) {
      this.presets = this.presets.filter(p => p.id !== id);
      this._persist();
    },

    rename(id, newName) {
      const p = this.presets.find(p => p.id === id);
      if (p) { p.name = newName; this._persist(); }
    },

    cycleColor(id) {
      const p = this.presets.find(p => p.id === id);
      if (!p) return;
      const idx = COLOR_PALETTE.indexOf(p.color);
      p.color = COLOR_PALETTE[(idx + 1) % COLOR_PALETTE.length];
      this._persist();
    },

    spriteUrl(name) { return spriteUrl(name); },

    async copyPaste(pokepaste, event) {
      try {
        await navigator.clipboard.writeText(pokepaste);
        const btn = event.target;
        const orig = btn.textContent;
        btn.textContent = '¡Copiado!';
        setTimeout(() => { btn.textContent = orig; }, 1500);
      } catch {}
    },
  };
}

function spriteUrl(name) {
  const gender = ['-male', '-female'];
  const regional = ['-alola', '-galar', '-hisui', '-paldea'];
  let base = name.toLowerCase();
  // Gender variants → use base species sprite (Showdown doesn't split by gender)
  for (const s of gender) {
    if (base.endsWith(s)) { base = base.slice(0, -s.length); break; }
  }
  let suffix = '';
  for (const s of regional) {
    if (base.endsWith(s)) { suffix = s; base = base.slice(0, -s.length); break; }
  }
  return `https://play.pokemonshowdown.com/sprites/dex/${base.replace(/-/g, '')}${suffix}.png`;
}

function metaTeams() {
  return {
    open: false,
    loaded: false,
    loading: false,
    error: false,
    teams: [],
    stale: false,

    async expand() {
      this.open = !this.open;
      if (this.open && !this.loaded) {
        this.loading = true;
        this.error = false;
        try {
          const res = await fetch('/meta-teams?regulation=M-A');
          const data = await res.json();
          this.teams = data.teams || [];
          this.stale = data.stale || false;
          this.loaded = true;
        } catch (e) {
          this.error = 'Error al cargar equipos del meta.';
        } finally {
          this.loading = false;
        }
      }
    },

    spriteUrl(name) { return spriteUrl(name); },

    async importTeam(team) {
      if (team.pokepaste_url && team.pokepaste_url.startsWith('https://pokepast.es/')) {
        try {
          const rawUrl = team.pokepaste_url.replace(/\/$/, '') + '/raw';
          const res = await fetch(rawUrl);
          if (res.ok) {
            const paste = await res.text();
            window.dispatchEvent(new CustomEvent('meta-prefill-import', { detail: { paste } }));
          }
        } catch {}
      } else if (team.members && team.members.length > 0) {
        // Fallback: pre-fill anchor with first member name
        const anchorEl = document.getElementById('anchor-input');
        if (anchorEl) {
          anchorEl.value = team.members[0].name;
          anchorEl.dispatchEvent(new Event('input'));
          anchorEl.scrollIntoView({ behavior: 'smooth' });
        }
      }
    },
  };
}

function tournaments() {
  return {
    open: false,
    loaded: false,
    loading: false,
    error: false,
    items: [],
    stale: false,
    lat: null,
    lon: null,
    _map: null,
    _marker: null,

    async expand() {
      this.open = !this.open;
      if (this.open) {
        await this.$nextTick();
        this.initMap();
        if (!this.loaded) await this.fetchTournaments();
      }
    },

    initMap() {
      if (this._map) {
        this._map.invalidateSize();
        return;
      }
      const mapEl = document.getElementById('tournament-map');
      if (!mapEl || typeof L === 'undefined') return;
      const defaultLat = 40.4168, defaultLon = -3.7038; // Madrid
      this._map = L.map(mapEl).setView([defaultLat, defaultLon], 5);
      L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
        maxZoom: 18,
      }).addTo(this._map);
      this._map.on('click', async (e) => {
        this.lat = e.latlng.lat;
        this.lon = e.latlng.lng;
        if (this._marker) this._map.removeLayer(this._marker);
        this._marker = L.marker([this.lat, this.lon]).addTo(this._map);
        await this.fetchTournaments();
      });
      // Force tile render after Alpine finishes showing the container
      setTimeout(() => this._map && this._map.invalidateSize(), 150);
    },

    geolocate() {
      if (!navigator.geolocation) { this.error = 'Geolocalización no disponible en este navegador.'; return; }
      navigator.geolocation.getCurrentPosition(
        async (pos) => {
          this.lat = pos.coords.latitude;
          this.lon = pos.coords.longitude;
          if (this._map) {
            this._map.setView([this.lat, this.lon], 10);
            if (this._marker) this._map.removeLayer(this._marker);
            this._marker = L.marker([this.lat, this.lon]).addTo(this._map);
          }
          await this.fetchTournaments();
        },
        () => { this.error = 'No se pudo obtener tu ubicación.'; }
      );
    },

    async fetchTournaments() {
      this.loading = true;
      this.error = false;
      try {
        let url = '/tournaments';
        if (this.lat !== null && this.lon !== null) {
          url += `?lat=${this.lat.toFixed(4)}&lon=${this.lon.toFixed(4)}`;
        }
        const res = await fetch(url);
        const data = await res.json();
        this.items = data.tournaments || [];
        this.stale = data.stale || false;
        this.loaded = true;
      } catch (e) {
        this.error = 'Error al cargar torneos.';
      } finally {
        this.loading = false;
      }
    },
  };
}
