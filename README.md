# stealth-site-cloner

A single-file Python script that renders the URLs listed in a `sitemap.xml` using a headless Chromium browser and writes the rendered HTML into a local directory tree.

CSS, JavaScript, and other assets in the saved HTML continue to load from their original origin. For complex SPA/WebGL pages, use `--settle-ms` and `--screenshots` to capture a visual migration reference.

Cross-platform: **Linux, macOS, and native Windows** (no WSL needed).

> **Use responsibly.** Run this only against URLs you own, URLs you operate, or URLs whose owners have given you explicit permission to render. You are responsible for compliance with the destination's terms of service and applicable law.

---

## What you get

```
./out/
├── index.html
├── about/index.html
├── contact/index.html
└── blog/post-1/index.html
```

Open any `index.html` in a browser.

---

## Requirements

| | Min version | Notes |
|---|---|---|
| Python | 3.10 | Comes with most Linux distros; use the python.org installer on Windows |
| pip | bundled | |
| Disk | ~200 MB | For the bundled Chromium that Playwright downloads |
| Internet | required | For the install, and for rendering pages live |

Optional — only for the design-summary extractor:

| | Min version |
|---|---|
| Node.js | 18 |
| npm | bundled |

The script does **not** require a system-level browser, sudo on Windows, Docker, or WSL.

---

## Install

### Linux / macOS

```bash
git clone https://github.com/sidhartha1s/stealth-site-cloner.git
cd stealth-site-cloner
bash scripts/install.sh
```

### Windows 10 / 11 (native)

```powershell
git clone https://github.com/sidhartha1s/stealth-site-cloner.git
cd stealth-site-cloner
powershell -ExecutionPolicy Bypass -File scripts\install.ps1
```

Step-by-step instructions per OS, with a Windows troubleshooting table, are in [docs/INSTALL.md](docs/INSTALL.md).

---

## Usage

```bash
python stealth_clone.py https://example.com/ --out ./out/
```

| Argument | Default | Description |
|---|---|---|
| `url` (positional) | required | Base URL to render |
| `--out` | `./stealth-clone` | Output directory |
| `--limit N` | `0` (all) | Cap the number of URLs to render |
| `--settle-ms N` | `2000` | Wait time after `DOMContentLoaded` before saving |
| `--screenshots` | off | Also save a viewport PNG next to each HTML file |

If the host has no `sitemap.xml`, the script falls back to rendering the single URL you passed.

More examples and internals: [docs/USAGE.md](docs/USAGE.md).

---

## Optional: extract a design summary

[skillui](https://www.npmjs.com/package/skillui) is a separate npm tool that produces a `DESIGN.md` summarising colours, fonts, components, and animations derived from a site's CSS.

```bash
npm install -g skillui
skillui --url https://example.com/ --name example --out ./design/ --no-skill
```

Details: [docs/DESIGN_EXTRACTION.md](docs/DESIGN_EXTRACTION.md).

---

## Use with Claude Code or Codex

A ready-made [agent skill](skills/clone-site/SKILL.md) lives in `skills/clone-site/`.

For Codex, copy it to:

- Linux/macOS: `~/.codex/skills/clone-site/`
- Windows: `%USERPROFILE%\.codex\skills\clone-site\`

For Claude Code, copy it to:

- Linux/macOS: `~/.claude/skills/clone-site/`
- Windows: `%USERPROFILE%\.claude\skills\clone-site\`

---

## Repository layout

```
stealth-site-cloner/
├── README.md
├── LICENSE                       MIT
├── stealth_clone.py              the renderer (single-file, ~135 lines)
├── requirements.txt              Python dependencies
├── .gitignore
├── docs/
│   ├── INSTALL.md                per-OS install with troubleshooting
│   ├── USAGE.md                  CLI flags, examples, internals
│   └── DESIGN_EXTRACTION.md      optional skillui add-on
├── scripts/
│   ├── install.sh                Linux / macOS one-shot installer
│   └── install.ps1               Windows PowerShell installer
└── skills/
    └── clone-site/
        └── SKILL.md              drop-in skill for Codex or Claude Code
```

---

## Security & responsible use

- The renderer writes only inside the directory passed via `--out`. Sitemap entries that try to escape this directory (including URL-encoded traversal and Windows path separators) are dropped, with a defence-in-depth check before each write.
- Sitemap XML is parsed with `defusedxml`, which disables external entities and blocks common XML attacks.
- Saved HTML includes a small replay shim so root-relative SPA and WebGL asset requests still resolve to the original host when opened from `file://`.
- The tool does not bypass paywalls, login walls, or DRM. Pages requiring a session will not render.
- The tool does not consult `robots.txt`. **Respect site owners.** Don't render at high concurrency against hosts you don't own.

---

## Disclaimer

This is a general-purpose page-rendering tool. Render only what you have the right to render. The maintainers accept no responsibility for misuse.

---

## License

MIT — see [LICENSE](LICENSE).
