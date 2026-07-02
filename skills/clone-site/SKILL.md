---
name: clone-site
description: Clone any live website into working local HTML files AND extract its design system (colors, fonts, components, animations). Use this whenever the user says "clone", "copy", "mirror", "download", or "scrape" a website, or wants to replicate a site's look and feel. Defaults to homepage-only clone; full-site sitemap walk is opt-in. Always verify the clone visually before sharing a port URL with the user.
---

# Clone Site

**SUPERSEDED (2026-07-03): all cloning now runs through the `site-migrator` pipeline** —
`~/Automation Projects/site-migrator/` (repo: `sidhartha1s/site-migrator`, see its README + PLAN.md).
This skill remains as the trigger + pointer; do NOT use the legacy scripts below.

## Why the old flow was retired

The legacy scripts (`~/flat_clone.py`, `~/stealth_clone.py`) saved `page.content()` — the
post-JS **serialized DOM**. That freezes widget state: dead datepickers, stuck hero sliders,
stale dates (proven on thesaibabahotel.com, 2026-07-02). site-migrator captures **raw server
HTML** instead, which the site's own CDN JS hydrates fresh, exactly like the live site.
It also captures the mobile template (Simplotel CMS serves different markup per UA) and
serves it UA-adaptively.

## Current flow

```bash
cd ~/Automation\ Projects/site-migrator

# 1. capture (homepage; add --sitemap for the full site)
python3 pipeline/capture.py <url> runs/<site> [--sitemap]

# 2. preview — capture dirs are ARCHIVES; never browse via file://
python3 pipeline/ua_server.py runs/<site> <port>   # then http://localhost:<port>/

# 3. verify (eyeball a screenshot first, then the tiers)
python3 pipeline/verify/t2_functional.py http://localhost:<port>/    # widgets work?
python3 pipeline/verify/t1_parity.py <bundle-dir> <live-url>         # skeleton parity
python3 pipeline/verify/t3_visual.py <bundle-dir> <clone-url> <live-url>  # pixel parity

# 4. ship bundle (AWS-ready flat layout + .htaccess + spec files) + security gate
python3 pipeline/bundle.py runs/<site> <live-url> runs/<site>-bundle
pipeline/verify/seccheck.sh runs/<site>-bundle bookings.<domain> [allowlist]
```

Rules that survive from this skill:
- **Never share a port URL before eyeballing the rendered output yourself.**
- Pages need internet + HTTP serving (CSS/JS load from the live CDN; `file://` breaks).
- REBUILD verdicts from the SPA detector are ADVISORY — check hydration parity
  clone-vs-live before concluding a page needs a rebuild.

## Design system extraction (unchanged, optional)

```bash
NODE_PATH=$(/home/sidhartha/.nvm/versions/node/v20.20.0/bin/npm root -g) \
  /home/sidhartha/.nvm/versions/node/v20.20.0/bin/skillui \
  --url <url> --name <domain> --out <dir> --no-skill
```

Caveat: skillui ingests third-party widget CSS variables (`--adp-*` air-datepicker,
`--iti-*` intl-tel-input) as brand tokens and can invert the theme — verify the palette
against computed styles on the rendered page before trusting DESIGN.md.

## Legacy scripts

`~/flat_clone.py`, `~/stealth_clone.py`, `~/verify_clone.py` — deprecated, kept only for
reference. Their capabilities are covered by `capture.py` / `ua_server.py` / the verify tiers.
