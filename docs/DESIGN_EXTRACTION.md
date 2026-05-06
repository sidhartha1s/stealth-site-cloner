# Optional: extract the design system

[skillui](https://www.npmjs.com/package/skillui) is a separate npm tool that reads a site's live CSS and produces a `DESIGN.md` summarising:

- Colour palette
- Font families and stacks
- Component patterns (buttons, cards, navs)
- Detected animations
- Grid baseline

It's independent of `stealth_clone.py` — runs in its own process and writes its own output folder. You can use one without the other.

---

## Install (one-time)

Requires Node.js 18+ and npm.

### Linux / macOS

```bash
# If you don't have Node:
#   Linux:  sudo apt install nodejs npm
#   macOS:  brew install node
npm install -g skillui
```

### Windows

1. Install Node.js LTS from https://nodejs.org/en/download (the installer puts `npm` on PATH automatically).
2. Open a new PowerShell:

```powershell
npm install -g skillui
```

---

## Run

```bash
skillui --url https://example.com/ --name example --out ./design/ --no-skill
```

| Flag | Why |
|---|---|
| `--url <url>` | The site to analyse |
| `--name <slug>` | Names the output sub-folder (`./design/<slug>-design/`) |
| `--out <dir>` | Where to write the design folder |
| `--no-skill` | Stops skillui from auto-installing the result as a Claude Code skill |

`--mode ultra` exists but tends to time out on JS-heavy sites — the default mode is reliable.

---

## Output

```
./design/example-design/
├── DESIGN.md          ← human-readable summary
├── tokens.json        ← colors / fonts / spacing as machine data
└── ...
```

Open `DESIGN.md` in any markdown viewer.

---

## Combined workflow with `stealth_clone.py`

A typical run that produces both the rendered pages and the design summary in one folder:

```bash
DOMAIN=example.com
python stealth_clone.py https://$DOMAIN/ --out ./cloned-$DOMAIN/stealth-pages/
skillui --url https://$DOMAIN/ --name $DOMAIN --out ./cloned-$DOMAIN/design/ --no-skill
```

Result:

```
./cloned-example.com/
├── stealth-pages/        ← rendered HTML
└── design/
    └── example.com-design/
        └── DESIGN.md
```

---

## Linux note

If `skillui` exits with `Cannot find module ...`, point Node at the global module root:

```bash
NODE_PATH=$(npm root -g) skillui --url ... --no-skill
```

---

## Cleanup

If you forgot `--no-skill`, remove the auto-installed Claude skill:

```bash
# Linux / macOS
rm -rf ~/.claude/skills/<name>/

# Windows PowerShell
Remove-Item -Recurse "$HOME\.claude\skills\<name>"
```
