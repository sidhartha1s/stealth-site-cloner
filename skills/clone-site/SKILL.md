---
name: clone-site
description: Render the URLs listed in a site's sitemap.xml into local HTML files using headless Chromium, and optionally produce a CSS-derived design summary. Use this when the user asks to render, snapshot, mirror, or capture a local copy of a site they own or have permission to render. Common phrasings include "clone", "copy", "mirror", "snapshot", or "capture" a site.
---

# Clone Site

Renders every URL of a sitemap to local HTML using `playwright-stealth`, plus optionally extracts a design summary via `skillui`.

## Dependencies

| Tool | Purpose |
|---|---|
| `stealth_clone.py` | Sitemap discovery + headless Chromium render |
| `playwright` (pip) | Headless Chromium |
| `playwright-stealth` (pip) | Robust headless rendering on sites that block default headless browsers |
| `defusedxml` (pip) | Safe sitemap XML parsing |
| `skillui` (npm, optional) | Design summary extraction |

Setup: see the repo's `docs/INSTALL.md`. The path to `stealth_clone.py` depends on where the user cloned the repo.

## Output structure

```
./<output-dir>/
  stealth-pages/   ← rendered HTML, URL directory structure preserved
  design/          ← DESIGN.md + tokens (only if skillui ran)
```

Pages in `stealth-pages/` link to the live CDN for CSS/JS — they render correctly in any browser when online.

## Steps

### 1. Render the sitemap

```bash
python stealth_clone.py <url> --out ./<output-dir>/stealth-pages/
```

Fetches `sitemap.xml`, discovers all URLs, renders each with a pool of 3 stealth browser pages. Output mirrors the URL structure.

Falls back to rendering the single supplied URL if no sitemap is found.

Useful flags:

- `--limit N` — cap the number of pages, e.g. for a smoke test
- The script accepts a single deep URL as the base — it will just render that one page

### 2. Extract design summary (optional)

```bash
skillui --url <url> --name <slug> --out ./<output-dir>/design/ --no-skill
```

`--no-skill` prevents auto-installing the design as a Claude skill. Default mode is reliable; `--mode ultra` tends to time out on JS-heavy sites.

If skillui can't find its modules on Linux:

```bash
NODE_PATH=$(npm root -g) skillui ...
```

Clean up any auto-installed Claude skill afterwards:

```bash
# Linux / macOS
rm -rf ~/.claude/skills/<slug>/
```

For Codex, install this bundled skill by copying `skills/clone-site/` to `~/.codex/skills/clone-site/` on Linux/macOS or `%USERPROFILE%\.codex\skills\clone-site\` on Windows.

### 3. Report

- **Pages:** `./<output-dir>/stealth-pages/` — open any `index.html` in a browser
- **Design:** `./<output-dir>/design/<slug>-design/DESIGN.md`
- Page count and any failures

## Notes

- Saved pages require an internet connection (CSS/JS load from the live origin).
- `CONCURRENCY` is hardcoded to 3 in `stealth_clone.py` — edit the constant if a host throttles.
- Single-URL renders (no sitemap) work via graceful fallback.
- Use only on URLs the user owns, operates, or has permission to render.
