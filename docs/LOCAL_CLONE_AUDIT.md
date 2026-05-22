# Local Clone Audit Lessons

This note records the local replay audit run against existing ignored
`cloned-*` outputs in this checkout on 2026-05-22. The purpose is to preserve
what worked in the best local clones and make repeat clone work easier to
verify.

Run command:

```bash
python3 scripts/audit_local_clones.py \
  --root /home/sidhartha/stealth-site-cloner \
  --out-dir /tmp/local-clone-audit
```

Use `--only 'cloned-n8n-*'` or another glob to rerun a focused subset.

If Playwright cannot launch Chrome in a restricted sandbox, rerun the command in
an environment where Chromium can start. The audit starts a short-lived local
HTTP server for each clone directory and writes screenshots plus
`local-clone-audit.json`.

## Result Groups

Clean local replays:

| Clone | Signal |
| --- | --- |
| `cloned-arkitek-final` | Text, images, canvas, and video rendered with no local asset errors. |
| `cloned-detroit-paris-home` | Video-heavy page rendered with no local asset errors. |
| `cloned-fromanother-love-v3` / `v4` | Later captures fixed earlier blank `fromanother` attempts. |
| `cloned-infracorp-global` | Nuxt/WebGL homepage replayed with local assets and no local errors. |
| `cloned-n8n-homepage` | Large static homepage replayed locally; console hydration noise did not block visual render. |
| `cloned-premium-nepal-stays-static-full` | Static origin worked; preview wrapper clones stayed on a loading shell. |
| `cloned-simplotel` | Directory-index site replayed cleanly after relative-link migration. |

Close but not perfect:

| Clone | Remaining replay gap |
| --- | --- |
| `cloned-notion` | DOM, text, images, and video render, but many local `_next/static/css` and font requests are missing. |
| `cloned-linear` | Main page renders, but Next RSC route probes such as `?_rsc=...` return local 404s. |
| `cloned-stripe` | Main page renders, but worker/source-attribution and notification endpoints are missing. |
| `cloned-sidewave-unity-fixed` | Better Sidewave attempt hydrates and renders text/canvas, but Unity DXT `.wasm.br` and `.data.br` variants are missing. |

Failed or obsolete attempts:

- Early `fromanother`, `new-studio`, `igloo`, and preview-wrapper clones either
  render blank, miss core WebGL assets, or preserve only a wrapper shell.
- The useful Premium Nepal clone is the static-origin output, not the preview
  wrapper output.
- Sidewave variants that time out during screenshot still contain a hydrated DOM,
  but they are not dependable review targets unless Unity build variants and
  tracker endpoints are neutralized.

## Reusable Rules

- Serve clones over HTTP before judging them. `file://` hides protocol, worker,
  and root-relative asset problems.
- Treat generated screenshots and browser metrics as the gate. HTML size alone
  is misleading for hydration-heavy sites.
- Keep a screenshot timeout from aborting the whole audit. Some WebGL/Unity pages
  wait on fonts or GPU state even when the DOM is populated.
- For framework sites, capture and rewrite query-string assets. Notion and
  Linear show that `_next/static`, font paths, and RSC probes are common replay
  gaps.
- For Unity/WebGL sites, capture compressed variants beside the base names:
  `.data.br`, `.wasm.br`, and DXT/ASTC variant names. Missing one can leave a
  mostly rendered DOM with a broken canvas.
- Strip or neutralize tracking endpoints such as Cloudflare RUM and analytics
  beacons before treating local 404/501 noise as product breakage.
- When a visible preview URL is just a loading wrapper, inspect frames/routes and
  find the static origin before calling the clone complete.
