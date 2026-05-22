"""Compare a live URL with a locally served clone using Playwright.

The script captures live/local screenshots for desktop and mobile viewports,
collects structural page metrics, and writes a JSON report. If Pillow is
installed, it also writes simple screenshot diff images.

Usage:
    python3 scripts/compare_live_local.py https://example.com/ http://127.0.0.1:8080/
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
from pathlib import Path

from playwright.async_api import async_playwright

try:
    from PIL import Image, ImageChops, ImageStat
except ImportError:  # pragma: no cover - optional visual diff dependency
    Image = None
    ImageChops = None
    ImageStat = None


VIEWPORTS = {
    "desktop": {"width": 1440, "height": 900},
    "mobile": {"width": 390, "height": 844},
}


async def maybe_dismiss_cookie(page):
    for label in ("Reject", "Accept"):
        try:
            button = page.get_by_role("button", name=label)
            if await button.count():
                await button.first.click(timeout=2000)
                await page.wait_for_timeout(500)
                return label
        except Exception:
            pass
    return None


async def capture(browser, name: str, url: str, viewport: dict[str, int], out_dir: Path, wait_ms: int):
    context = await browser.new_context(
        viewport=viewport,
        device_scale_factor=1,
        ignore_https_errors=True,
    )
    page = await context.new_page()
    failed_requests = []
    http_errors = []
    console_errors = []
    page.on(
        "requestfailed",
        lambda request: failed_requests.append({"url": request.url, "error": str(request.failure)}),
    )
    page.on(
        "response",
        lambda response: http_errors.append({"url": response.url, "status": response.status})
        if response.status >= 400
        else None,
    )
    page.on(
        "console",
        lambda message: console_errors.append(message.text)
        if message.type in ("error", "warning")
        else None,
    )

    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=45000)
        await page.wait_for_timeout(wait_ms)
    except Exception as exc:
        failed_requests.append({"url": url, "error": f"goto/wait: {exc}"})

    cookie_action = await maybe_dismiss_cookie(page)
    await page.wait_for_timeout(2500)

    screenshot_path = out_dir / f"{name}.png"
    await page.screenshot(path=str(screenshot_path), full_page=False, animations="allow")
    metrics = await page.evaluate(
        """() => {
          const clean = s => (s || '').replace(/\\s+/g, ' ').trim();
          const text = clean(document.body.innerText);
          const headings = [...document.querySelectorAll('h1,h2,h3')]
            .map(el => clean(el.innerText)).filter(Boolean).slice(0, 30);
          const visibleHeadings = [...document.querySelectorAll('h1,h2,h3')]
            .filter(el => {
              const r = el.getBoundingClientRect();
              const cs = getComputedStyle(el);
              return r.width > 0 && r.height > 0 && r.bottom > 0 && r.right > 0 &&
                r.top < innerHeight && r.left < innerWidth && cs.visibility !== 'hidden' &&
                cs.display !== 'none' && Number(cs.opacity) !== 0;
            })
            .map(el => clean(el.innerText)).filter(Boolean).slice(0, 12);
          return {
            title: document.title,
            bodyTextLength: text.length,
            textSample: text.slice(0, 240),
            headings,
            visibleHeadings,
            canvasCount: document.querySelectorAll('canvas').length,
            videoCount: document.querySelectorAll('video').length,
            imageCount: document.querySelectorAll('img').length,
            stylesheetCount: document.querySelectorAll('link[rel="stylesheet"], style').length,
            scriptCount: document.querySelectorAll('script[src]').length,
            scrollHeight: document.documentElement.scrollHeight,
            bodyBg: getComputedStyle(document.body).backgroundColor,
          };
        }"""
    )
    text_for_hash = await page.evaluate("() => (document.body.innerText || '').replace(/\\s+/g, ' ').trim()")
    metrics["bodyTextHash"] = hashlib.sha256(text_for_hash.encode("utf-8")).hexdigest()
    metrics["cookieAction"] = cookie_action
    metrics["failedRequests"] = failed_requests[:40]
    metrics["httpErrors"] = http_errors[:40]
    metrics["consoleErrors"] = console_errors[:40]
    metrics["screenshot"] = str(screenshot_path)
    await context.close()
    return metrics


def image_delta(left_path: str, right_path: str, diff_path: Path):
    if Image is None:
        return {"skipped": "Pillow is not installed"}

    left = Image.open(left_path).convert("RGB")
    right = Image.open(right_path).convert("RGB")
    if left.size != right.size:
        right = right.resize(left.size)
    diff = ImageChops.difference(left, right)
    diff.save(diff_path)
    stat = ImageStat.Stat(diff)
    mean_abs = sum(stat.mean) / 3
    diff_pixels = 0
    total = left.size[0] * left.size[1]
    pixels = diff.load()
    for y in range(left.size[1]):
        for x in range(left.size[0]):
            if max(pixels[x, y]) > 30:
                diff_pixels += 1
    return {
        "meanAbsRgbDiff": round(mean_abs, 2),
        "pixelsDifferentPct": round(diff_pixels * 100 / total, 2),
        "diffImage": str(diff_path),
    }


async def launch_browser(playwright):
    attempts = [
        {
            "headless": True,
            "executable_path": "/usr/bin/google-chrome",
            "args": ["--no-sandbox", "--disable-dev-shm-usage", "--disable-crash-reporter"],
        },
        {
            "headless": True,
            "args": ["--no-sandbox", "--disable-dev-shm-usage", "--disable-crash-reporter"],
        },
    ]
    last_error = None
    for options in attempts:
        try:
            return await playwright.chromium.launch(**options)
        except Exception as exc:
            last_error = exc
    raise last_error


def summarize(results):
    summary = {}
    for viewport_name, result in results.items():
        live = result["live"]
        local = result["local"]
        live_headings = set(live["headings"])
        local_headings = set(local["headings"])
        summary[viewport_name] = {
            "titleMatch": live["title"] == local["title"],
            "bodyTextHashMatch": live["bodyTextHash"] == local["bodyTextHash"],
            "headingOverlap": len(live_headings & local_headings),
            "liveHeadingCount": len(live_headings),
            "localHeadingCount": len(local_headings),
            "canvasMatch": live["canvasCount"] == local["canvasCount"],
            "videoMatch": live["videoCount"] == local["videoCount"],
            "imageMatch": live["imageCount"] == local["imageCount"],
            "localFailedRequestCount": len(local["failedRequests"]),
            "localHttpErrorCount": len(local["httpErrors"]),
            "imageDelta": result["imageDelta"],
        }
    return summary


async def run(args):
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    async with async_playwright() as playwright:
        browser = await launch_browser(playwright)
        results = {}
        for viewport_name, viewport in VIEWPORTS.items():
            live = await capture(browser, f"{viewport_name}-live", args.live_url, viewport, out_dir, args.wait_ms)
            local = await capture(browser, f"{viewport_name}-local", args.local_url, viewport, out_dir, args.wait_ms)
            delta = image_delta(live["screenshot"], local["screenshot"], out_dir / f"{viewport_name}-diff.png")
            results[viewport_name] = {"live": live, "local": local, "imageDelta": delta}
        await browser.close()

    payload = {"summary": summarize(results), "details": results}
    report_path = out_dir / "comparison.json"
    report_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload["summary"], indent=2))
    print(f"REPORT={report_path}")


def main():
    parser = argparse.ArgumentParser(description="Compare a live site with a locally served clone")
    parser.add_argument("live_url", help="Live URL, e.g. https://example.com/")
    parser.add_argument("local_url", help="Local clone URL, e.g. http://127.0.0.1:8080/")
    parser.add_argument("--out-dir", default="/tmp/clone-playwright-compare", help="Directory for screenshots and JSON")
    parser.add_argument("--wait-ms", type=int, default=12000, help="Post-DOMContentLoaded wait before capture")
    args = parser.parse_args()
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
