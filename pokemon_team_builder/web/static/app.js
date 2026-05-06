function app() {
  return {
    anchor: '',
    variants: '3',
    loading: false,
    error: '',
    results: [],

    init() {},

    async generate() {
      this.error = '';
      this.results = [];
      this.loading = true;
      try {
        const res = await fetch('/generate', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ anchor: this.anchor.trim().toLowerCase(), variants: parseInt(this.variants) }),
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

    capitalize(str) {
      return str.replace(/-/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
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
  };
}
