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

## Current flow — one command

```bash
cd ~/Automation\ Projects/site-migrator

# capture -> serve -> T2 (clone+live) -> T1 -> T3 -> run-report.json,
# then STOPS and asks "Bundle for AWS upload?"
python3 pipeline/migrate.py <url> [--homepage] [--quick]

# on the user's yes, re-run extended through ship bundle + seccheck:
python3 pipeline/migrate.py <url> --bundle bookings.<domain>[,<domain2>]
```

Read `runs/<site>/run-report.json` after the run; eyeball whatever it flags
(REBUILD advisories, T3 over-threshold folds, seccheck holds). Individual
stages remain runnable solo — see the repo README for the per-stage commands
(capture.py / ua_server.py / verify/* / bundle.py).

Rules that survive from this skill:
- **Ask before bundling (standing preference, 2026-07-03): when the clone is done and
  verified, ask the user "Bundle for AWS upload?" — do NOT run bundle.py unprompted.**
  Cloning and shipping are separate decisions; the bundle step also needs their
  booking-domain list and allowlist sign-offs.
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
