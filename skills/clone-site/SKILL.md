---
name: clone-site
description: Clone any live website into working local HTML files AND extract its design system (colors, fonts, components, animations). Use this whenever the user says "clone", "copy", "mirror", "download", or "scrape" a website, or wants to replicate a site's look and feel. Defaults to flat homepage-only clone; full-site sitemap walk is opt-in. Always verify the clone visually before sharing a port URL with the user.
---

# Clone Site

Clones a live website using playwright-stealth and extracts its design system via skillui. **Default = flat homepage only.** Sitemap walking is opt-in.

## Dependencies

| Tool | Path | Purpose |
|------|------|---------|
| `flat_clone.py` | `~/flat_clone.py` | **Default.** Single-URL flat render → `<outdir>/index.html` |
| `stealth_clone.py` | `~/stealth_clone.py` | Opt-in. Sitemap discovery + path-preserving render of every URL |
| `verify_clone.py` | `~/verify_clone.py` | Headless screenshot + DOM heuristics — **mandatory before sharing a port** |
| `playwright-stealth` | pip | Bot-detection bypass |
| `playwright` | pip + npm global | Headless Chromium |
| `skillui` | global npm | Design system extraction |

## Output structure

```
./cloned-<domain>/
  index.html       ← flat homepage (default mode)
  # OR (full-site mode):
  stealth-pages/   ← every URL, path-preserved (our-story/index.html, tents/eden/index.html, ...)
  design/          ← DESIGN.md + design tokens
```

CSS/JS inside the cloned HTML still points at the live CDN — pages need **internet + an HTTP server** to render. `file://` breaks protocol-relative URLs (`//cdn.example.com/...`).

## Steps

### 1. Clone

**Default — flat homepage only:**

```bash
python3 ~/flat_clone.py <url> ./cloned-<domain>/
```

Saves a single `index.html` at the output root. No path nesting, no sitemap walking. Use this unless the user explicitly asks for "every page" or "full site".

**Opt-in — full-site sitemap walk** (only when user asks):

```bash
python3 ~/stealth_clone.py <url> --out ./cloned-<domain>/stealth-pages/
```

Fetches `sitemap.xml`, renders each URL with a pool of 3 stealth pages. Output mirrors URL structure. **Heads-up:** `stripe.com/in` saves to `in/index.html`, so serving `./cloned-stripe/` shows a directory listing — point the user at `http://localhost:PORT/in/` or use flat mode.

### 2. Serve

```bash
cd ./cloned-<domain>/ && python3 -m http.server <PORT>
```

Run in background. Pages need HTTP serving, not `file://`.

### 3. Verify before sharing — MANDATORY

**Never share a port URL with the user before you have eyeballed the rendered output yourself.** The user will be furious. Run:

```bash
python3 ~/verify_clone.py http://localhost:<PORT>/ /tmp/verify_<domain>.png
```

Then `Read` the screenshot. Decide:

- **Pass:** styled, recognizable, looks like the live site → share the port URL.
- **Fail:** unstyled vertical list, raw text dump, directory listing, blank page, single giant element → kill the port, do not share. Tell the user what went wrong.

Heuristic JSON output (cssLinks, docH, hasFlex, visibleTextLen) is a hint, not a gate. **Client-hydrated SPAs (Notion, many React apps) can pass every heuristic and still render as a broken DOM** — visual inspection is the only reliable check.

### 4. Extract design system (optional, only when user asks for design)

```bash
NODE_PATH=$(npm root -g) skillui --url <url> --name <domain> \
  --out ./cloned-<domain>/design/ --no-skill
```

`--no-skill` prevents auto-installing as a Claude skill. Default mode only — `--mode ultra` times out on JS-heavy sites.

Clean up any auto-installed skill:
```bash
ls ~/.claude/skills/<domain>/ 2>/dev/null && \
  rm ~/.claude/skills/<domain>/SKILL.md && rmdir ~/.claude/skills/<domain>/
```

### 5. Report

- **Port URL** — only after verify step passes
- **Local path** — `./cloned-<domain>/index.html` (or `stealth-pages/` for full-site)
- **Design** — `./cloned-<domain>/design/DESIGN.md` if extracted
- **Known failures** — name any pages that failed to render

## Known failure modes

- **Client-side hydration nukes the DOM** (Notion-style React apps) — server-rendered HTML is replaced on load with a broken tree. No fix in this skill. Tell the user; suggest they pick a less hydration-heavy target.
- **Protocol-relative URLs under `file://`** — always serve over HTTP.
- **Directory listing on full-site clones** — sitemap mode saves `stripe.com/in` to `in/index.html`. Serve from the right subpath or use flat mode.
- **Bot detection** — `stealth_clone.py` auto-drops concurrency from 3 to 1 if challenges trigger. If still blocked, flat mode + manual User-Agent already in `flat_clone.py` usually works.

## Notes

- Pages require an internet connection (CSS/JS load from the live CDN).
- Flat mode is the default because users almost always mean "show me the homepage", not "walk 200 URLs".
- Never share an unverified port URL. The user has called this out explicitly. Verify, then share.
