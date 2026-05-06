"""
Renders the URLs listed in a site's sitemap.xml into local HTML files
using headless Chromium (playwright + playwright-stealth).

CSS/JS links remain external (they continue to point at the original
origin), so saved pages render correctly in any browser when online.

Use only on URLs you own, operate, or have permission to render.
"""

import asyncio
import argparse
from pathlib import Path
from urllib.parse import unquote, urlparse

import requests
from defusedxml import ElementTree as ET
from playwright.async_api import async_playwright
from playwright_stealth import Stealth

SITEMAP_NS = "http://www.sitemaps.org/schemas/sitemap/0.9"
CONCURRENCY = 3  # parallel pages (each gets its own browser page)
MAX_SITEMAP_BYTES = 25 * 1024 * 1024  # 25 MB cap per sitemap response
ALLOWED_SCHEMES = ("http", "https")
WINDOWS_UNSAFE_CHARS = set('<>:"|?*')


def _normalized_port(parsed) -> int | None:
    """Return the explicit port or the default for http(s)."""
    try:
        if parsed.port is not None:
            return parsed.port
    except ValueError:
        return None
    if parsed.scheme == "http":
        return 80
    if parsed.scheme == "https":
        return 443
    return None


def _same_origin(candidate: str, base_host: str, base_scheme: str, base_port: int) -> bool:
    """Allow only http(s) URLs whose scheme, host, and port match the base."""
    try:
        p = urlparse(candidate)
    except ValueError:
        return False
    if p.scheme not in ALLOWED_SCHEMES:
        return False
    if p.scheme != base_scheme:
        return False
    return p.hostname == base_host and _normalized_port(p) == base_port


def _fetch_capped(url: str) -> bytes | None:
    """GET with a hard size cap to avoid runaway sitemap payloads."""
    try:
        with requests.get(url, timeout=20, stream=True) as resp:
            resp.raise_for_status()
            buf = bytearray()
            for chunk in resp.iter_content(chunk_size=64 * 1024):
                if not chunk:
                    continue
                buf.extend(chunk)
                if len(buf) > MAX_SITEMAP_BYTES:
                    print(f"  ⚠ {url} exceeded {MAX_SITEMAP_BYTES} bytes — skipped")
                    return None
            return bytes(buf)
    except Exception as e:
        print(f"  ⚠ Could not fetch {url}: {e}")
        return None


def fetch_sitemap_urls(sitemap_url: str, base_host: str, base_scheme: str, base_port: int,
                       seen: set[str] | None = None) -> list[str]:
    """Recursively fetch all page URLs from a sitemap or sitemap index.

    Filters out cross-origin and non-http(s) entries to prevent the renderer
    from being aimed at unrelated hosts via a hostile sitemap.
    """
    if seen is None:
        seen = set()
    if sitemap_url in seen:
        return []
    seen.add(sitemap_url)

    body = _fetch_capped(sitemap_url)
    if body is None:
        return []

    try:
        root = ET.fromstring(body)
    except ET.ParseError as e:
        print(f"  ⚠ Could not parse {sitemap_url}: {e}")
        return []

    tag = root.tag.split("}")[-1] if "}" in root.tag else root.tag

    if tag == "sitemapindex":
        urls: list[str] = []
        for loc in root.findall(f"{{{SITEMAP_NS}}}sitemap/{{{SITEMAP_NS}}}loc"):
            child = (loc.text or "").strip()
            if not child or not _same_origin(child, base_host, base_scheme, base_port):
                if child:
                    print(f"  ⚠ Skipping cross-origin sub-sitemap: {child}")
                continue
            print(f"  → Sub-sitemap: {child}")
            urls.extend(fetch_sitemap_urls(child, base_host, base_scheme, base_port, seen))
        return urls

    out: list[str] = []
    for loc in root.findall(f"{{{SITEMAP_NS}}}url/{{{SITEMAP_NS}}}loc"):
        u = (loc.text or "").strip()
        if not u:
            continue
        if not _same_origin(u, base_host, base_scheme, base_port):
            print(f"  ⚠ Skipping cross-origin URL: {u}")
            continue
        out.append(u)
    return out


def url_to_path(url: str) -> Path | None:
    """Convert a URL to a relative file path preserving directory structure.

    Returns None if every path component would be unsafe (``..``/``.``/empty).
    """
    parsed = urlparse(url)
    raw = unquote(parsed.path).replace("\\", "/").strip("/")
    if not raw:
        return Path("index.html")

    parts = [
        p
        for p in raw.split("/")
        if p
        and p not in ("..", ".")
        and not any(ord(ch) < 32 for ch in p)
        and not any(ch in WINDOWS_UNSAFE_CHARS for ch in p)
    ]
    if not parts:
        return None

    last = parts[-1]
    if last.lower().endswith((".html", ".htm")):
        return Path(*parts)
    return Path(*parts) / "index.html"


async def render_page(page, url: str, out_dir: Path):
    rel = url_to_path(url)
    if rel is None:
        print(f"  ✗ {url} — unsafe path, skipped")
        return False

    out_path = (out_dir / rel).resolve()
    try:
        out_path.relative_to(out_dir.resolve())
    except ValueError:
        print(f"  ✗ {url} — path escapes output dir, skipped")
        return False

    out_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=60000)
        await page.wait_for_timeout(2000)  # let JS settle
        out_path.write_text(await page.content(), encoding="utf-8")
        print(f"  ✓ {url}")
        return True
    except Exception as e:
        print(f"  ✗ {url} — {e}")
        return False


async def worker(queue: asyncio.Queue, browser, out_dir: Path):
    """Each worker owns its own page and pulls URLs from the shared queue."""
    page = await browser.new_page()
    results = []
    while True:
        try:
            url = queue.get_nowait()
        except asyncio.QueueEmpty:
            break
        results.append(await render_page(page, url, out_dir))
        queue.task_done()
    await page.close()
    return results


async def clone(base_url: str, out_dir: Path, limit: int = 0):
    parsed_base = urlparse(base_url)
    if parsed_base.scheme not in ALLOWED_SCHEMES or not parsed_base.hostname:
        raise SystemExit(f"Refusing to render non-http(s) URL: {base_url}")
    base_port = _normalized_port(parsed_base)
    if base_port is None:
        raise SystemExit(f"Refusing to render URL with invalid port: {base_url}")
    base_host = parsed_base.hostname
    base_scheme = parsed_base.scheme

    out_dir.mkdir(parents=True, exist_ok=True)

    sitemap_url = base_url.rstrip("/") + "/sitemap.xml"
    print(f"Fetching sitemap: {sitemap_url}")
    urls = fetch_sitemap_urls(sitemap_url, base_host, base_scheme, base_port)

    if not urls:
        print("No URLs found in sitemap — falling back to the supplied URL.")
        urls = [base_url]
    else:
        print(f"Found {len(urls)} URLs\n")

    if limit > 0:
        urls = urls[:limit]
        print(f"Limiting to first {len(urls)} URLs\n")

    queue: asyncio.Queue = asyncio.Queue()
    for url in urls:
        await queue.put(url)

    async with Stealth().use_async(async_playwright()) as p:
        browser = await p.chromium.launch(headless=True)
        workers = [worker(queue, browser, out_dir) for _ in range(CONCURRENCY)]
        all_results = await asyncio.gather(*workers)
        await browser.close()

    results = [r for batch in all_results for r in batch]
    print(f"\nDone — {sum(results)}/{len(urls)} pages saved to {out_dir}/")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Sitemap-driven page renderer")
    parser.add_argument("url", help="Base URL (e.g. https://example.com/)")
    parser.add_argument("--out", default="./stealth-clone", help="Output directory")
    parser.add_argument("--limit", type=int, default=0, help="Max URLs to render (0 = all)")
    args = parser.parse_args()

    asyncio.run(clone(args.url, Path(args.out), args.limit))
