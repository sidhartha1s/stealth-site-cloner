"""
Renders the URLs listed in a site's sitemap.xml into local HTML files
using headless Chromium (playwright + playwright-stealth).

CSS/JS links remain external (they continue to point at the original
origin), so saved pages render correctly in any browser when online.

Use only on URLs you own, operate, or have permission to render.
"""

import asyncio
import argparse
from html import escape, unescape
import json
from pathlib import Path
import re
from urllib.parse import unquote, urljoin, urlparse

import requests
from defusedxml import ElementTree as ET
from playwright.async_api import async_playwright
from playwright_stealth import Stealth

SITEMAP_NS = "http://www.sitemaps.org/schemas/sitemap/0.9"
CONCURRENCY = 3  # parallel pages (each gets its own browser page)
MAX_SITEMAP_BYTES = 25 * 1024 * 1024  # 25 MB cap per sitemap response
MAX_ASSET_BYTES = 100 * 1024 * 1024  # 100 MB cap per captured asset
ALLOWED_SCHEMES = ("http", "https")
WINDOWS_UNSAFE_CHARS = set('<>:"|?*')
HEAD_RE = re.compile(r"<head\b[^>]*>", re.IGNORECASE)
HEAD_CLOSE_RE = re.compile(r"</head\s*>", re.IGNORECASE)
BASE_RE = re.compile(r"<base\b", re.IGNORECASE)
HTML_URL_RE = re.compile(r"""(?:src|href)=["']([^"']+)["']|url\(["']?([^"')]+)["']?\)""",
                         re.IGNORECASE)
JS_ASSET_RE = re.compile(
    r"""["'`]([A-Za-z0-9_./-]+\.(?:drc|ktx2|wasm|json|exr|png|jpe?g|webp|js|"""
    r"""woff2?|glb|gltf|bin|ogg|mp3|mp4|webm|svg|br|gz|data|symbols|mem))["'`]""",
    re.IGNORECASE,
)
IMAGE_EXTENSIONS = ("png", "jpg", "jpeg", "webp", "ktx2", "exr", "svg")
AUDIO_EXTENSIONS = ("ogg", "mp3")
GEOMETRY_EXTENSIONS = ("drc",)
FONT_EXTENSIONS = ("json", "woff", "woff2")
BASIS_EXTENSIONS = ("wasm", "js")
GLTF_EXTENSIONS = ("glb", "gltf", "bin")


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


def url_to_asset_path(url: str) -> Path | None:
    """Convert a same-origin asset URL to a relative output path."""
    parsed = urlparse(url)
    raw = unquote(parsed.path).replace("\\", "/").strip("/")
    if not raw:
        return None

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
    return Path(*parts)


def origin_base_href(url: str) -> str:
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}/"


def replay_url_patch(url: str) -> str:
    origin = origin_base_href(url).rstrip("/")
    origin_json = json.dumps(origin)
    return f"""<script>
(() => {{
  const origin = {origin_json};
  const absolutize = (url) => {{
    if (typeof url === "string" && url.startsWith("/")) return origin + url;
    if (url instanceof URL && url.protocol === "file:" && url.pathname.startsWith("/")) {{
      return origin + url.pathname + url.search + url.hash;
    }}
    return url;
  }};

  const originalFetch = window.fetch;
  window.fetch = function(input, init) {{
    if (typeof input === "string" || input instanceof URL) {{
      input = absolutize(input);
    }} else if (input instanceof Request && input.url.startsWith("file:///")) {{
      const parsed = new URL(input.url);
      input = new Request(origin + parsed.pathname + parsed.search + parsed.hash, input);
    }}
    return originalFetch.call(this, input, init);
  }};

  const OriginalWorker = window.Worker;
  window.Worker = function(scriptURL, options) {{
    const resolved = absolutize(scriptURL);
    try {{
      return new OriginalWorker(resolved, options);
    }} catch (error) {{
      if (typeof resolved !== "string" || !/^https?:\\/\\//.test(resolved)) throw error;
      const isModule = options && options.type === "module";
      const source = isModule
        ? `import ${{JSON.stringify(resolved)}};`
        : `importScripts(${{JSON.stringify(resolved)}});`;
      const blobURL = URL.createObjectURL(new Blob([source], {{ type: "text/javascript" }}));
      return new OriginalWorker(blobURL, options);
    }}
  }};
  window.Worker.prototype = OriginalWorker.prototype;

  const originalOpen = XMLHttpRequest.prototype.open;
  XMLHttpRequest.prototype.open = function(method, url, ...rest) {{
    return originalOpen.call(this, method, absolutize(url), ...rest);
  }};
}})();
</script>"""


def inject_base_href(html: str, url: str) -> str:
    """Make root-relative SPA asset fetches work when replayed from file://."""
    head = HEAD_RE.search(html)
    if not head:
        return html

    head_close = HEAD_CLOSE_RE.search(html, head.end())
    head_body = html[head.end():head_close.start()] if head_close else html[head.end():]
    if BASE_RE.search(head_body):
        return html

    replay_patch = replay_url_patch(url)
    base = f'<base href="{escape(origin_base_href(url), quote=True)}">'
    return html[:head.end()] + base + replay_patch + html[head.end():]


def rewrite_same_origin_urls(html: str, url: str) -> str:
    """Rewrite absolute same-origin URLs to root-relative URLs for local HTTP replay."""
    origin = origin_base_href(url).rstrip("/")
    return html.replace(origin, "")


def prepare_html(html: str, url: str, capture_assets: bool) -> str:
    if capture_assets:
        return rewrite_same_origin_urls(html, url)
    return inject_base_href(html, url)


class AssetCapture:
    def __init__(self, out_dir: Path, base_host: str, base_scheme: str, base_port: int):
        self.out_dir = out_dir
        self.base_host = base_host
        self.base_scheme = base_scheme
        self.base_port = base_port
        self._seen: set[str] = set()
        self._tasks: set[asyncio.Task] = set()
        self._lock = asyncio.Lock()
        self.manifest: list[dict[str, str | int]] = []

    def attach(self, page) -> None:
        page.on("response", lambda response: self.schedule(response))

    def schedule(self, response) -> None:
        task = asyncio.create_task(self.save_response(response))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def drain(self) -> None:
        while self._tasks:
            await asyncio.gather(*list(self._tasks), return_exceptions=True)

    async def save_response(self, response) -> None:
        request = response.request
        if request.method != "GET" or response.status != 200:
            return
        if request.resource_type == "document":
            return
        content_type = response.headers.get("content-type", "")
        if content_type.split(";", 1)[0].strip().lower() == "text/html":
            return
        if not _same_origin(response.url, self.base_host, self.base_scheme, self.base_port):
            return

        rel = url_to_asset_path(response.url)
        if rel is None:
            return

        out_path = (self.out_dir / rel).resolve()
        try:
            out_path.relative_to(self.out_dir.resolve())
        except ValueError:
            return

        async with self._lock:
            if response.url in self._seen:
                return
            self._seen.add(response.url)

        try:
            body = await response.body()
        except Exception:
            return
        self.save_bytes(response.url, rel, out_path, body, content_type)

    def save_bytes(self, url: str, rel: Path, out_path: Path, body: bytes, content_type: str) -> None:
        if not body:
            return
        if out_path.exists() and out_path.is_dir():
            return
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(body)
        self.manifest.append({
            "url": url,
            "path": str(rel),
            "bytes": len(body),
            "content_type": content_type,
        })

    async def capture_html_references(self, html: str, page_url: str) -> None:
        urls: list[str] = []
        for match in HTML_URL_RE.finditer(html):
            raw = match.group(1) or match.group(2) or ""
            raw = unescape(raw)
            if not raw or raw.startswith(("data:", "blob:", "#")):
                continue
            absolute = urljoin(page_url, raw)
            if _same_origin(absolute, self.base_host, self.base_scheme, self.base_port):
                urls.append(absolute)

        for url in sorted(set(urls)):
            await asyncio.to_thread(self.capture_url_sync, url)

    def capture_url_sync(self, url: str, quiet: bool = False) -> None:
        rel = url_to_asset_path(url)
        if rel is None:
            return
        out_path = (self.out_dir / rel).resolve()
        try:
            out_path.relative_to(self.out_dir.resolve())
        except ValueError:
            return

        if url in self._seen:
            return

        last_error: Exception | None = None
        for _ in range(2):
            try:
                with requests.get(url, timeout=20, stream=True) as resp:
                    resp.raise_for_status()
                    buf = bytearray()
                    for chunk in resp.iter_content(chunk_size=64 * 1024):
                        if not chunk:
                            continue
                        buf.extend(chunk)
                        if len(buf) > MAX_ASSET_BYTES:
                            print(f"  ⚠ {url} exceeded {MAX_ASSET_BYTES} bytes — skipped")
                            return
                    if url in self._seen:
                        return
                    self._seen.add(url)
                    self.save_bytes(url, rel, out_path, bytes(buf), resp.headers.get("content-type", ""))
                    return
            except Exception as e:
                last_error = e
        if last_error is not None and not quiet:
            print(f"  ⚠ Could not capture asset {url}: {last_error}")

    async def capture_js_references(self, page_url: str) -> None:
        js_files = sorted({Path(str(item["path"])) for item in self.manifest
                           if str(item["path"]).lower().endswith(".js")})
        for rel in js_files:
            js_path = self.out_dir / rel
            try:
                body = js_path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            urls: set[str] = set()
            for match in JS_ASSET_RE.finditer(body):
                raw = match.group(1)
                urls.update(self.candidate_asset_urls(raw, page_url))
            for url in sorted(urls):
                await asyncio.to_thread(self.capture_url_sync, url, True)

    def candidate_asset_urls(self, raw: str, page_url: str) -> set[str]:
        if raw.startswith(("http://", "https://")):
            return {raw} if _same_origin(raw, self.base_host, self.base_scheme, self.base_port) else set()
        if raw.startswith("//"):
            absolute = f"{self.base_scheme}:{raw}"
            return {absolute} if _same_origin(absolute, self.base_host, self.base_scheme, self.base_port) else set()
        if raw.startswith("/"):
            return {urljoin(page_url, raw)}
        if raw.startswith("./"):
            raw = raw[2:]
        if raw.startswith("../"):
            return set()
        if raw.startswith("assets/"):
            return {urljoin(page_url, "/" + raw)}
        if raw.startswith("Build/"):
            return {urljoin(page_url, "/" + raw)}

        ext = raw.rsplit(".", 1)[-1].lower()
        prefixes: list[str] = ["/assets/"]
        if ext in ("br", "gz", "data", "symbols", "mem"):
            prefixes.insert(0, "/Build/")
        if ext in IMAGE_EXTENSIONS:
            prefixes.insert(0, "/assets/images/")
        if ext in AUDIO_EXTENSIONS:
            prefixes.insert(0, "/assets/audio/")
        if ext in GEOMETRY_EXTENSIONS:
            prefixes.insert(0, "/assets/geometries/")
        if ext in FONT_EXTENSIONS:
            prefixes.insert(0, "/assets/fonts/")
        if ext in BASIS_EXTENSIONS:
            prefixes = ["/assets/libs/basis/", "/assets/libs/draco/", "/assets/"]
        if ext in GLTF_EXTENSIONS:
            prefixes.insert(0, "/assets/gltf/")
        return {urljoin(page_url, prefix + raw) for prefix in prefixes}

    def write_manifest(self) -> None:
        if not self.manifest:
            return
        manifest_path = self.out_dir / "asset-manifest.json"
        rows = sorted(self.manifest, key=lambda item: str(item["path"]))
        manifest_path.write_text(json.dumps(rows, indent=2), encoding="utf-8")


async def render_page(page, url: str, out_dir: Path, settle_ms: int, screenshots: bool,
                      capture_assets: bool, asset_capture: AssetCapture | None):
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
        await page.wait_for_timeout(settle_ms)  # let JS settle
        if asset_capture is not None:
            await asset_capture.drain()
        html = await page.content()
        if asset_capture is not None:
            await asset_capture.capture_html_references(html, url)
        out_path.write_text(prepare_html(html, url, capture_assets), encoding="utf-8")
        if screenshots:
            await page.screenshot(path=out_path.with_suffix(".png"))
        print(f"  ✓ {url}")
        return True
    except Exception as e:
        print(f"  ✗ {url} — {e}")
        return False


async def worker(queue: asyncio.Queue, browser, out_dir: Path, settle_ms: int, screenshots: bool,
                 capture_assets: bool, asset_capture: AssetCapture | None):
    """Each worker owns its own page and pulls URLs from the shared queue."""
    page = await browser.new_page()
    if asset_capture is not None:
        asset_capture.attach(page)
    results = []
    while True:
        try:
            url = queue.get_nowait()
        except asyncio.QueueEmpty:
            break
        results.append(await render_page(page, url, out_dir, settle_ms, screenshots,
                                         capture_assets, asset_capture))
        queue.task_done()
    await page.close()
    return results


async def clone(base_url: str, out_dir: Path, limit: int = 0, settle_ms: int = 2000,
                screenshots: bool = False, capture_assets: bool = False):
    parsed_base = urlparse(base_url)
    if parsed_base.scheme not in ALLOWED_SCHEMES or not parsed_base.hostname:
        raise SystemExit(f"Refusing to render non-http(s) URL: {base_url}")
    if settle_ms < 0:
        raise SystemExit("--settle-ms must be 0 or greater")
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

    asset_capture = (
        AssetCapture(out_dir, base_host, base_scheme, base_port)
        if capture_assets
        else None
    )

    async with Stealth().use_async(async_playwright()) as p:
        browser = await p.chromium.launch(headless=True)
        workers = [
            worker(queue, browser, out_dir, settle_ms, screenshots, capture_assets, asset_capture)
            for _ in range(CONCURRENCY)
        ]
        all_results = await asyncio.gather(*workers)
        if asset_capture is not None:
            await asset_capture.drain()
        await browser.close()

    if asset_capture is not None:
        await asset_capture.capture_js_references(base_url)
        asset_capture.write_manifest()

    results = [r for batch in all_results for r in batch]
    print(f"\nDone — {sum(results)}/{len(urls)} pages saved to {out_dir}/")
    if asset_capture is not None:
        print(f"Captured {len(asset_capture.manifest)} same-origin assets.")
        print(f"Replay with: cd {out_dir} && python3 -m http.server 8080")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Sitemap-driven page renderer")
    parser.add_argument("url", help="Base URL (e.g. https://example.com/)")
    parser.add_argument("--out", default="./stealth-clone", help="Output directory")
    parser.add_argument("--limit", type=int, default=0, help="Max URLs to render (0 = all)")
    parser.add_argument("--settle-ms", type=int, default=2000,
                        help="Milliseconds to wait after DOMContentLoaded before saving")
    parser.add_argument("--screenshots", action="store_true",
                        help="Also save a viewport PNG next to each rendered HTML file")
    parser.add_argument("--capture-assets", action="store_true",
                        help="Save same-origin runtime assets for local HTTP replay")
    args = parser.parse_args()

    asyncio.run(clone(args.url, Path(args.out), args.limit, args.settle_ms,
                      args.screenshots, args.capture_assets))
