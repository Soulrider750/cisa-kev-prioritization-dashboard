"""Generate the browser-side search page for a validated KEV release."""

from __future__ import annotations

from importlib import resources
from pathlib import Path

from .export import atomic_write_text


SEARCH_HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta
    http-equiv="Content-Security-Policy"
    content="default-src 'none'; style-src 'unsafe-inline'; script-src 'self'; connect-src 'self'; base-uri 'none'; form-action 'none'"
  >
  <title>Search CISA KEV Catalog</title>
  <style>
    :root {
      color-scheme: dark;
      --background: #07111f;
      --panel: #101d2d;
      --panel-raised: #15263a;
      --border: #2a3e55;
      --text: #e7eef7;
      --muted: #a7b7c9;
      --accent: #38bdf8;
      --warning: #fbbf24;
    }

    * { box-sizing: border-box; }
    [hidden] { display: none !important; }

    body {
      margin: 0;
      background: var(--background);
      color: var(--text);
      font-family: system-ui, -apple-system, BlinkMacSystemFont,
        "Segoe UI", sans-serif;
      font-size: 16px;
      line-height: 1.55;
    }

    main {
      width: min(1180px, calc(100% - 32px));
      margin: 0 auto;
      padding: 48px 0 80px;
    }

    a { color: #7dd3fc; }

    .site-nav {
      display: flex;
      flex-wrap: wrap;
      gap: 14px;
      margin-bottom: 28px;
    }

    .site-nav a {
      display: inline-block;
      padding: 8px 12px;
      border: 1px solid var(--border);
      border-radius: 8px;
      text-decoration: none;
    }

    .site-nav a:hover,
    .site-nav a:focus-visible,
    .site-nav a[aria-current="page"] {
      background: var(--panel-raised);
      text-decoration: underline;
    }

    h1 {
      max-width: 900px;
      margin: 8px 0 16px;
      font-size: clamp(2rem, 5vw, 3.5rem);
      line-height: 1.08;
    }

    h2 { margin: 0 0 16px; font-size: 1.65rem; }
    h3 { margin: 0 0 8px; font-size: 1.18rem; }
    p { margin-top: 0; }

    .eyebrow {
      margin: 0;
      color: var(--accent);
      font-size: 0.85rem;
      font-weight: 750;
      letter-spacing: 0.1em;
      text-transform: uppercase;
    }

    .lede {
      max-width: 80ch;
      color: var(--muted);
      font-size: 1.08rem;
    }

    .catalog-meta { color: var(--muted); }

    .notice {
      margin: 24px 0;
      padding: 18px;
      background: var(--panel-raised);
      border: 1px solid var(--border);
      border-left: 5px solid var(--warning);
      border-radius: 8px;
    }

    .panel,
    .record {
      padding: 22px;
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 12px;
    }

    fieldset {
      min-width: 0;
      margin: 0;
      padding: 0;
      border: 0;
    }

    fieldset:disabled { opacity: 0.65; }

    .filters {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      gap: 16px;
    }

    .field-wide { grid-column: 1 / -1; }

    label {
      display: block;
      margin-bottom: 5px;
      font-weight: 650;
    }

    input,
    select,
    button {
      font: inherit;
    }

    input,
    select {
      width: 100%;
      min-height: 44px;
      padding: 8px 11px;
      color: var(--text);
      background: var(--background);
      border: 1px solid #58718d;
      border-radius: 8px;
    }

    input:focus-visible,
    select:focus-visible,
    button:focus-visible,
    summary:focus-visible,
    a:focus-visible {
      outline: 3px solid var(--accent);
      outline-offset: 2px;
    }

    .hint {
      margin: 5px 0 0;
      color: var(--muted);
      font-size: 0.88rem;
    }

    .actions {
      display: flex;
      align-items: center;
      flex-wrap: wrap;
      gap: 12px;
      margin-top: 18px;
    }

    button {
      min-height: 44px;
      padding: 8px 14px;
      color: var(--text);
      background: var(--panel-raised);
      border: 1px solid #58718d;
      border-radius: 8px;
      cursor: pointer;
    }

    button:hover:not(:disabled) { background: #1d344d; }
    button:disabled { opacity: 0.55; cursor: not-allowed; }

    .results-heading {
      display: flex;
      flex-wrap: wrap;
      align-items: baseline;
      justify-content: space-between;
      gap: 12px;
      margin: 44px 0 16px;
    }

    .results-heading h2,
    .results-heading p { margin: 0; }

    .results-list {
      display: grid;
      gap: 14px;
    }

    .record-heading {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      align-items: baseline;
    }

    .record-heading code {
      color: #bae6fd;
      font-size: 1.05rem;
      font-weight: 750;
    }

    .record-name {
      font-weight: 650;
    }

    .record-facts {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
      gap: 8px 18px;
      margin: 14px 0;
    }

    .record-facts div,
    .record-details div { min-width: 0; }

    dt {
      color: var(--muted);
      font-size: 0.84rem;
      font-weight: 700;
      letter-spacing: 0.03em;
      text-transform: uppercase;
    }

    dd {
      margin: 2px 0 0;
      overflow-wrap: anywhere;
    }

    details {
      padding-top: 12px;
      border-top: 1px solid var(--border);
    }

    summary { cursor: pointer; color: #7dd3fc; }

    .record-details {
      display: grid;
      gap: 12px;
      margin: 14px 0 0;
    }

    .pagination {
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      gap: 12px;
      margin-top: 22px;
    }

    .empty {
      padding: 24px;
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 12px;
    }

    footer {
      margin-top: 52px;
      padding-top: 22px;
      color: var(--muted);
      border-top: 1px solid var(--border);
    }

    @media (max-width: 700px) {
      main {
        width: min(100% - 20px, 1180px);
        padding-top: 28px;
      }

      .panel,
      .record { padding: 16px; }
    }
  </style>
  <script src="search.js" defer></script>
</head>
<body>
  <main>
    <nav class="site-nav" aria-label="Site pages">
      <a href="index.html">Dashboard</a>
      <a href="search.html" aria-current="page">Search catalog</a>
    </nav>

    <header>
      <p class="eyebrow">Vulnerability intelligence</p>
      <h1>Search the CISA KEV catalog</h1>
      <p class="lede">
        Explore every entry in the current validated catalog snapshot.
        Search across catalog text or combine specific filters.
      </p>
      <p id="catalog-meta" class="catalog-meta" aria-live="polite">
        Loading catalog details…
      </p>
    </header>

    <aside class="notice">
      <strong>Interpretation:</strong>
      A KEV entry confirms that CISA has documented exploitation of the
      vulnerability. It does not establish whether a particular organization
      uses the affected product. Ransomware use marked Unknown is not evidence
      that ransomware use is absent.
    </aside>

    <section class="panel" aria-labelledby="filter-heading">
      <h2 id="filter-heading">Filter vulnerabilities</h2>
      <form id="filters" role="search">
        <fieldset id="filter-fields" disabled>
          <div class="filters">
            <div class="field-wide">
              <label for="query">Search all catalog fields</label>
              <input id="query" name="query" type="search"
                autocomplete="off" placeholder="CVE, name, description, action, notes…">
              <p class="hint">Matches catalog text without regard to case.</p>
            </div>
            <div>
              <label for="cve">CVE ID</label>
              <input id="cve" name="cve" type="search"
                autocomplete="off" placeholder="CVE-2026-…">
            </div>
            <div>
              <label for="vendor">Vendor</label>
              <input id="vendor" name="vendor" type="search"
                autocomplete="off" placeholder="Vendor name">
            </div>
            <div>
              <label for="product">Product</label>
              <input id="product" name="product" type="search"
                autocomplete="off" placeholder="Product name">
            </div>
            <div>
              <label for="ransomware">Known ransomware campaign use</label>
              <select id="ransomware" name="ransomware">
                <option value="">All statuses</option>
                <option value="Known">Known</option>
                <option value="Unknown">Unknown</option>
              </select>
            </div>
            <div>
              <label for="cwe">CWE</label>
              <input id="cwe" name="cwe" type="search"
                autocomplete="off" placeholder="CWE-79">
            </div>
            <div>
              <label for="date-from">Added on or after</label>
              <input id="date-from" name="date-from" type="date">
            </div>
            <div>
              <label for="date-to">Added on or before</label>
              <input id="date-to" name="date-to" type="date">
            </div>
          </div>
          <div class="actions">
            <button type="reset">Clear filters</button>
            <span class="hint">Results update as you type.</span>
          </div>
        </fieldset>
      </form>
      <noscript>
        <p>Enable JavaScript to search the catalog. The full dataset is
          available as a
          <a href="data/vulnerabilities.csv">CSV download</a>.</p>
      </noscript>
    </section>

    <section aria-labelledby="results-heading">
      <div class="results-heading">
        <h2 id="results-heading">Results</h2>
        <p id="result-count" role="status" aria-live="polite">
          Loading catalog…
        </p>
      </div>
      <p class="hint">
        <a href="data/vulnerabilities.csv" download>Download full catalog CSV</a>
        (all entries, regardless of filters).
      </p>
      <div id="error" class="empty" hidden>
        <p>Could not load the catalog. Check your connection and try again.</p>
        <button id="retry" type="button">Retry</button>
      </div>
      <p id="empty" class="empty" hidden>
        No entries match these filters. Try clearing or broadening them.
      </p>
      <div id="results" class="results-list" aria-label="Matching vulnerabilities"></div>
      <nav id="pagination" class="pagination" aria-label="Result pages" hidden>
        <button id="previous" type="button">Previous</button>
        <span id="page-status" aria-live="polite"></span>
        <button id="next" type="button">Next</button>
      </nav>
    </section>

    <footer>
      Independent analysis of public CISA data. This project is not
      affiliated with or endorsed by CISA. Search results are catalog
      entries, not an organization-specific risk assessment.
    </footer>
  </main>
</body>
</html>
"""


def render_search_page(output_dir: Path) -> tuple[Path, Path]:
    """Write a search page and its packaged, same-origin JavaScript."""

    page_path = output_dir / "search.html"
    script_path = output_dir / "search.js"
    script_text = (
        resources.files("kev_dashboard")
        .joinpath("static/search.js")
        .read_text(encoding="utf-8")
    )

    atomic_write_text(page_path, SEARCH_HTML)
    atomic_write_text(script_path, script_text)

    return page_path, script_path
