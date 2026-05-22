"""Render a single URL with playwright-stealth, save flat to <outdir>/index.html.

Use when the user wants just the homepage — no sitemap walking, no path nesting.
The cloned page's CSS/JS point at the live CDN, so it needs internet + a real
HTTP server (not file://) to render correctly.

Usage:
    python3 ~/flat_clone.py <url> <outdir>
"""
import asyncio, sys
from pathlib import Path
from playwright.async_api import async_playwright
from playwright_stealth import Stealth


async def go(url: str, outdir: str):
    out = Path(outdir)
    out.mkdir(parents=True, exist_ok=True)
    async with Stealth().use_async(async_playwright()) as p:
        browser = await p.chromium.launch(headless=True)
        ctx = await browser.new_context(
            viewport={"width": 1440, "height": 900},
            user_agent=(
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
            ),
        )
        page = await ctx.new_page()
        await page.goto(url, wait_until="networkidle", timeout=60000)
        await page.wait_for_timeout(2500)
        html = await page.content()
        (out / "index.html").write_text(html, encoding="utf-8")
        print(f"✓ {url} -> {out}/index.html ({len(html)} bytes)")
        await browser.close()


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("usage: flat_clone.py <url> <outdir>", file=sys.stderr)
        sys.exit(2)
    asyncio.run(go(sys.argv[1], sys.argv[2]))
