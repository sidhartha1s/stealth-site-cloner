# Playwright Live-vs-Local Comparison

Use `scripts/compare_live_local.py` after serving a captured clone over HTTP.
It loads the live URL and the local clone at desktop and mobile viewports,
captures screenshots, records page metrics, and writes `comparison.json`.

```bash
cd cloned-example
python3 -m http.server 8080

cd ..
python3 scripts/compare_live_local.py \
  https://example.com/ \
  http://127.0.0.1:8080/ \
  --out-dir /tmp/example-compare
```

The comparison is intended to catch blank pages, broken hydration, missing
assets, and major layout drift. For animated WebGL or video-backed pages, expect
some pixel-level difference between live and local captures; title, text hash,
heading overlap, asset counts, canvas counts, and HTTP errors are usually the
more stable pass/fail signals.

If Chrome fails with a Linux sandbox or crashpad error in a restricted
environment, rerun the comparison where Playwright is allowed to launch a
browser. This is an environment limitation, not a clone-rendering failure.

## Infracorp Global Check

On 2026-05-22, `https://infracorp.global/` exposed one URL in
`/sitemap.xml`. A stealth clone with asset capture saved the homepage plus 79
same-origin assets, including Nuxt bundles, fonts, WebGL particle models,
Draco WASM, audio, earth textures, and partner images.

Validation command:

```bash
python3 scripts/compare_live_local.py \
  https://infracorp.global/ \
  http://127.0.0.1:8081/ \
  --out-dir cloned-infracorp-global/playwright-comparison
```

Result summary from the first capture:

| Viewport | Title | Text hash | Headings | Canvas/video/image counts | Local HTTP errors | Visual delta |
| --- | --- | --- | --- | --- | --- | --- |
| Desktop | match | match | 30/30 overlap | match | 0 | 0.01% pixels |
| Mobile | match | match | 30/30 overlap | match | 0 | 0.0% pixels |

In a follow-up run with the reusable script, the structural checks were still
identical while desktop visual delta rose to 7.21% because the WebGL scene had
advanced to a different animation state. Treat visual delta as supporting
evidence on animated pages, not as the only pass/fail gate.

The only local request failures were aborted Google Analytics collection calls,
which also occurred on the live site and did not affect rendering.
