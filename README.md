# stealth-site-cloner

A single-file Python script that renders every URL in a site's `sitemap.xml` with a headless Chromium browser and writes the rendered HTML into a local directory tree.

> **Use responsibly.** Run this only against URLs you own, operate, or have explicit permission to render. You are responsible for compliance with the destination's terms of service and applicable law.

## What it does

- `stealth_clone.py`: walks `sitemap.xml`, renders each URL with Playwright (+ `playwright-stealth`), and saves the rendered HTML to `./out/<path>/index.html`. CSS, JS, and other assets keep loading from their original origin. Falls back to rendering the single URL you passed if the host has no sitemap.
- For complex SPA/WebGL pages, `--settle-ms` and `--screenshots` capture a visual migration reference, and `--capture-assets` saves same-origin JS, workers, WASM, images, fonts, and runtime assets for local HTTP replay.
- `flat_clone.py` / `verify_clone.py`: helper scripts for a flat homepage clone and clone verification (see `docs/`).
- `scripts/audit_local_clones.py` / `scripts/compare_live_local.py`: audit previously generated `cloned-*` output, and compare a served clone against the live page with Playwright screenshots and DOM metrics.
- Cross-platform: Linux, macOS, and native Windows, no WSL needed.

## Quick start

```bash
git clone https://github.com/sidhartha1s/stealth-site-cloner.git
cd stealth-site-cloner
bash scripts/install.sh          # Linux/macOS
# powershell -ExecutionPolicy Bypass -File scripts\install.ps1   # Windows

python stealth_clone.py https://example.com/ --out ./out/
```

Key flags: `--limit N` (cap URLs rendered), `--single-page` (skip sitemap discovery), `--settle-ms N` (default 2000, wait after `DOMContentLoaded`), `--screenshots`, `--capture-assets`. Full flag table and examples in `docs/USAGE.md`.

For WebGL/SPA output, serve it instead of opening the file directly:

```bash
python stealth_clone.py https://example.com/ --out ./cloned-example/ --single-page --settle-ms 30000 --screenshots --capture-assets
cd cloned-example
python3 -m http.server 8080
```

## Layout

| Path | Role |
|---|---|
| `stealth_clone.py` | The renderer: sitemap walk, single-file, ~135 lines |
| `flat_clone.py` | Flat homepage clone helper |
| `verify_clone.py` | Clone verification helper |
| `scripts/install.sh`, `scripts/install.ps1` | Per-OS installers |
| `scripts/audit_local_clones.py` | Audits previously generated `cloned-*` output |
| `scripts/compare_live_local.py` | Compares a served clone against the live page |
| `docs/INSTALL.md` | Per-OS install steps, Windows troubleshooting table |
| `docs/USAGE.md` | CLI flags, examples, internals |
| `docs/DESIGN_EXTRACTION.md` | Optional `skillui` design-summary add-on |
| `docs/PLAYWRIGHT_COMPARISON.md`, `docs/LOCAL_CLONE_AUDIT.md` | Comparison and audit walkthroughs |
| `skills/clone-site/SKILL.md` | Drop-in agent skill for Claude Code or Codex |

## Notes / gotchas

- Requires Python 3.10+ and Playwright's bundled Chromium (~200 MB disk, downloaded on install). Node.js 18+ only needed for the optional `skillui` design extractor (`npm install -g skillui`).
- No system-level browser, sudo on Windows, Docker, or WSL required.
- The renderer writes only inside the `--out` directory; sitemap entries attempting path traversal (including URL-encoded and Windows-separator variants) are dropped with a defence-in-depth check before each write.
- Sitemap XML is parsed with `defusedxml`, which disables external entities.
- Saved HTML includes a small replay shim so root-relative SPA/WebGL asset requests still resolve to the original host when opened from `file://`.
- Does not bypass paywalls, login walls, or DRM, and does not consult `robots.txt`; don't render at high concurrency against hosts you don't own.
- MIT licensed (`LICENSE` present in the repo).

## Related repos

[site-migrator](https://github.com/sidhartha1s/site-migrator) states in its own README that it supersedes the `clone-site` skill family, naming `stealth_clone.py` specifically: its `capture.py --sitemap` replaces this repo's sitemap walk and adds crash-safe resume. Nothing in this repo says so, so treat site-migrator as the newer pipeline and this one as kept for the lighter single-file rendering case.
