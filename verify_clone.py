"""Screenshot a locally served clone and emit pass/fail heuristics.

Usage:
    python3 ~/verify_clone.py <local-url> <screenshot-path>

Prints a one-line verdict + JSON metrics. Exit code 0 always — the caller (or
the human) decides PASS/FAIL after eyeballing the screenshot. Heuristics are
hints, not gates: client-hydrated sites can wipe the DOM and still pass naive
checks.
"""
import asyncio, json, sys
from playwright.async_api import async_playwright


async def main(url: str, shot_path: str):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        ctx = await browser.new_context(viewport={"width": 1440, "height": 900})
        page = await ctx.new_page()
        try:
            await page.goto(url, wait_until="networkidle", timeout=45000)
        except Exception as e:
            print(f"LOAD_ERROR {e}")
        await page.wait_for_timeout(2500)
        await page.screenshot(path=shot_path, full_page=False)
        info = await page.evaluate(
            """() => {
              const bg = getComputedStyle(document.body).backgroundColor;
              const cssLinks = document.querySelectorAll('link[rel=stylesheet]').length;
              const docH = document.documentElement.scrollHeight;
              const imgs = document.querySelectorAll('img').length;
              const hasFlex = [...document.querySelectorAll('*')]
                .some(e => getComputedStyle(e).display === 'flex');
              const visibleTextLen = (document.body.innerText || '').trim().length;
              return {bg, cssLinks, docH, imgs, hasFlex, visibleTextLen};
            }"""
        )
        print(f"SHOT={shot_path}")
        print(json.dumps(info))
        await browser.close()


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("usage: verify_clone.py <local-url> <screenshot-path>", file=sys.stderr)
        sys.exit(2)
    asyncio.run(main(sys.argv[1], sys.argv[2]))
