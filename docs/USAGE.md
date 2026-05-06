# Usage

## Synopsis

```bash
python stealth_clone.py <BASE_URL> [--out OUT_DIR] [--limit N]
```

| Argument | Default | Description |
|---|---|---|
| `url` (positional) | required | Base URL to render (e.g. `https://example.com/`) |
| `--out` | `./stealth-clone` | Output directory (created if missing) |
| `--limit N` | `0` (all URLs) | Render at most `N` URLs from the sitemap |

The script never prompts; it runs to completion or exits non-zero on a hard failure.

> **Use responsibly.** Render only URLs you own, operate, or have permission to render.

---

## Examples

### Smoke test (one page only)

```bash
python stealth_clone.py https://example.com/ --limit 1 --out ./_test/
```

Useful for verifying the install — Chromium boots, the stealth patches load, and one HTML file appears at `_test/index.html`.

### Whole-sitemap render

```bash
python stealth_clone.py https://example.com/ --out ./out/
```

Output:

```
Fetching sitemap: https://example.com/sitemap.xml
Found N URLs

  ✓ https://example.com/
  ✓ https://example.com/about
  ...

Done — N/N pages saved to ./out/
```

### Single deep page

```bash
python stealth_clone.py https://example.com/about --out ./out/
```

The script first looks for `https://example.com/about/sitemap.xml`. When that 404s, it falls back to rendering just the URL you passed.

### Multiple targeted pages

The script doesn't accept multiple URLs in one invocation. Re-run it for each page; outputs into the same `--out` dir merge cleanly because paths are derived from the URL:

```bash
python stealth_clone.py https://example.com/ --out ./out/
python stealth_clone.py https://example.com/about --out ./out/
python stealth_clone.py https://example.com/legal/privacy --out ./out/
```

---

## Output structure

```
./out/
├── index.html                    ← from https://example.com/
├── about/index.html              ← from https://example.com/about
├── blog/post-1.html              ← from https://example.com/blog/post-1.html
└── docs/getting-started/index.html
```

URL-to-path rule:

| URL ending | File path |
|---|---|
| `/` (root) | `index.html` |
| `/foo` | `foo/index.html` |
| `/foo/bar` | `foo/bar/index.html` |
| `/foo/page.html` | `foo/page.html` |
| `/foo/page.htm` | `foo/page.htm` |

Path components that would escape `--out` (including URL-encoded traversal and Windows path separators) are dropped; the renderer also performs a final `is_relative_to(out_dir)` check before each write.

---

## How it works

1. **Sitemap discovery.** Fetches `<BASE_URL>/sitemap.xml`. If the response is a `<sitemapindex>`, follows each child sitemap recursively. If no sitemap is found, falls back to rendering the single base URL. XML is parsed with `defusedxml`.
2. **One browser, multiple pages.** Spins up a single headless Chromium with `playwright-stealth` patches applied. A pool of 3 worker pages pulls URLs from a shared queue.
3. **Render.** Each page is loaded with `wait_until="domcontentloaded"`, then a 2-second JS-settle delay, then `page.content()` is written to disk. CSS, images, fonts, and JS are **not** downloaded — the rendered HTML still references them at their original URLs.
4. **Mirror.** The URL path is preserved verbatim under `--out`, after path-traversal sanitisation.

---

## Tuning

The script is intentionally tiny (~135 lines). Tune by editing constants near the top of `stealth_clone.py`:

| Constant | Default | What it controls |
|---|---|---|
| `CONCURRENCY` | `3` | Parallel browser pages. Lower it if you're hitting a host that throttles. |

For longer JS-settle delay (single-page apps that load content async), edit `render_page`:

```python
await page.wait_for_timeout(2000)  # bump this
```

Or wait on a specific selector:

```python
await page.wait_for_selector("main", timeout=10000)
```

---

## Caveats

- **Saved pages still load CSS/JS from the live origin.** They render correctly in any browser when online; they look broken offline. The goal is a faithful render, not an offline mirror.
- **No asset download.** Images, videos, fonts, JS bundles — none of these are saved locally.
- **Robots and rate limits.** This tool does not consult `robots.txt`. Render only what you have the right to render, and don't run high concurrency against hosts you don't own.
- **Session-gated content.** Pages that require login won't render correctly — Playwright launches a clean browser context every run.
- **Query strings.** The path-mapping ignores query strings; two URLs differing only in `?foo=bar` will overwrite each other.

---

## Exit codes

| Code | Meaning |
|---|---|
| 0 | Run completed (some pages may have failed individually — check the per-URL ✓/✗ lines) |
| non-zero | Hard failure (Python error, Chromium failed to launch, etc.) |
