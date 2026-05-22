"""Audit locally saved clone folders with Playwright.

The script finds ``cloned-*`` directories that contain a root ``index.html`` or
``stealth-pages/index.html``, serves each directory over HTTP, captures a
desktop screenshot, and writes JSON metrics. It is meant for comparing old clone
attempts and spotting replay gaps such as missing local assets, blank WebGL
renders, and hydration-only pages.

Usage:
    python3 scripts/audit_local_clones.py --root . --out-dir /tmp/local-clone-audit
"""

from __future__ import annotations

import argparse
import asyncio
import fnmatch
import json
import socket
import subprocess
import time
from pathlib import Path

from playwright.async_api import async_playwright

try:
    from PIL import Image, ImageStat
except ImportError:  # pragma: no cover - optional screenshot scoring
    Image = None
    ImageStat = None


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def discover_candidates(root: Path, only_patterns: list[str]):
    for clone_dir in sorted(root.glob("cloned-*")):
        if not clone_dir.is_dir():
            continue
        if only_patterns and not any(fnmatch.fnmatch(clone_dir.name, pattern) for pattern in only_patterns):
            continue
        if (clone_dir / "index.html").exists():
            yield clone_dir.name, clone_dir, "/"
        elif (clone_dir / "stealth-pages" / "index.html").exists():
            yield clone_dir.name, clone_dir / "stealth-pages", "/"


def start_server(directory: Path, port: int) -> subprocess.Popen:
    return subprocess.Popen(
        ["python3", "-m", "http.server", str(port), "--bind", "127.0.0.1"],
        cwd=str(directory),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


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


def screenshot_stats(path: Path) -> dict:
    if Image is None or not path.exists():
        return {"bytes": path.stat().st_size if path.exists() else 0}

    image = Image.open(path).convert("RGB")
    stat = ImageStat.Stat(image)
    return {
        "bytes": path.stat().st_size,
        "meanRgb": [round(value, 2) for value in stat.mean],
        "stddevRgb": [round(value, 2) for value in stat.stddev],
        "extrema": image.getextrema(),
    }


def score_result(metrics: dict, stats: dict, local_errors: list, http_errors: list, screenshot_error: str | None):
    score = "pass"
    reasons = []

    if metrics["bodyTextLength"] < 50 and metrics["images"] == 0 and metrics["canvas"] == 0:
        score = "fail"
        reasons.append("very little text and no visual media")

    screenshot_bytes = stats.get("bytes", 0)
    max_stddev = max(stats.get("stddevRgb", [0]))
    if screenshot_bytes < 20_000 or max_stddev < 4:
        score = "fail"
        reasons.append("screenshot appears blank or low-detail")

    if local_errors or http_errors:
        score = "warn" if score == "pass" else score
        reasons.append("local asset errors")

    if screenshot_error:
        score = "warn" if score == "pass" else score
        reasons.append("screenshot timeout")

    return score, reasons


async def audit_one(browser, name: str, serve_dir: Path, path: str, out_dir: Path, wait_ms: int):
    port = free_port()
    proc = start_server(serve_dir, port)
    time.sleep(0.6)
    url = f"http://127.0.0.1:{port}{path}"
    failed = []
    http_errors = []
    console = []
    context = None

    try:
        context = await browser.new_context(viewport={"width": 1440, "height": 900}, device_scale_factor=1)
        page = await context.new_page()
        page.on("requestfailed", lambda request: failed.append({"url": request.url, "error": str(request.failure)}))
        page.on(
            "response",
            lambda response: http_errors.append({"url": response.url, "status": response.status})
            if response.url.startswith(f"http://127.0.0.1:{port}") and response.status >= 400
            else None,
        )
        page.on(
            "console",
            lambda message: console.append({"type": message.type, "text": message.text[:240]})
            if message.type in ("error", "warning")
            else None,
        )

        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=45000)
            await page.wait_for_timeout(wait_ms)
        except Exception as exc:
            failed.append({"url": url, "error": f"goto/wait: {exc}"})

        screenshot_path = out_dir / f"{name}.png"
        screenshot_error = None
        try:
            await page.screenshot(
                path=str(screenshot_path),
                full_page=False,
                animations="allow",
                timeout=12000,
            )
        except Exception as exc:
            screenshot_error = str(exc)

        metrics = await page.evaluate(
            """() => {
              const clean = s => (s || '').replace(/\\s+/g, ' ').trim();
              const text = clean(document.body.innerText);
              const visibleText = [...document.querySelectorAll('body *')]
                .filter(el => {
                  const r = el.getBoundingClientRect();
                  const cs = getComputedStyle(el);
                  return r.width > 0 && r.height > 0 && r.bottom > 0 && r.right > 0 &&
                    r.top < innerHeight && r.left < innerWidth && cs.visibility !== 'hidden' &&
                    cs.display !== 'none' && Number(cs.opacity) !== 0;
                })
                .map(el => clean(el.innerText)).filter(Boolean).join(' ').slice(0, 300);
              return {
                title: document.title,
                bodyTextLength: text.length,
                textSample: text.slice(0, 220),
                visibleTextSample: visibleText,
                cssLinks: document.querySelectorAll('link[rel="stylesheet"], style').length,
                scripts: document.querySelectorAll('script[src]').length,
                images: document.querySelectorAll('img').length,
                canvas: document.querySelectorAll('canvas').length,
                videos: document.querySelectorAll('video').length,
                iframes: document.querySelectorAll('iframe').length,
                scrollHeight: document.documentElement.scrollHeight,
                bodyBg: getComputedStyle(document.body).backgroundColor,
                rootChildren: document.body.children.length,
              };
            }"""
        )
        stats = screenshot_stats(screenshot_path)
        local_failed = [
            item
            for item in failed
            if item["url"].startswith(f"http://127.0.0.1:{port}")
        ]
        score, reasons = score_result(metrics, stats, local_failed, http_errors, screenshot_error)
        return {
            "name": name,
            "serveDir": str(serve_dir),
            "url": url,
            "score": score,
            "reasons": reasons,
            "metrics": metrics,
            "screenshotStats": stats,
            "screenshotError": screenshot_error,
            "failedRequests": failed[:25],
            "localFailedRequests": local_failed[:25],
            "httpErrors": http_errors[:25],
            "console": console[:20],
            "screenshot": str(screenshot_path),
        }
    finally:
        if context is not None:
            await context.close()
        proc.terminate()
        try:
            proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            proc.kill()


def summarize(results: list[dict]) -> list[dict]:
    rows = []
    for result in results:
        stats = result["screenshotStats"]
        rows.append(
            {
                "name": result["name"],
                "score": result["score"],
                "title": result["metrics"]["title"],
                "text": result["metrics"]["bodyTextLength"],
                "images": result["metrics"]["images"],
                "canvas": result["metrics"]["canvas"],
                "videos": result["metrics"]["videos"],
                "localErrors": len(result["localFailedRequests"]) + len(result["httpErrors"]),
                "shotBytes": stats.get("bytes", 0),
                "stddev": max(stats.get("stddevRgb", [0])),
                "reasons": result["reasons"],
            }
        )
    return rows


async def run(args):
    root = Path(args.root)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    candidates = list(discover_candidates(root, args.only))
    results = []
    partial_path = out_dir / "local-clone-audit.partial.json"

    async with async_playwright() as playwright:
        browser = await launch_browser(playwright)
        for name, serve_dir, path in candidates:
            print(f"auditing {name}", flush=True)
            results.append(await audit_one(browser, name, serve_dir, path, out_dir, args.wait_ms))
            partial_path.write_text(json.dumps(results, indent=2), encoding="utf-8")
        await browser.close()

    report_path = out_dir / "local-clone-audit.json"
    report_path.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(json.dumps(summarize(results), indent=2))
    print(f"REPORT={report_path}")


def main():
    parser = argparse.ArgumentParser(description="Audit local cloned-* directories with Playwright")
    parser.add_argument("--root", default=".", help="Repository or parent directory containing cloned-* folders")
    parser.add_argument("--out-dir", default="/tmp/local-clone-audit", help="Directory for screenshots and JSON")
    parser.add_argument("--wait-ms", type=int, default=9000, help="Post-DOMContentLoaded wait before capture")
    parser.add_argument("--only", action="append", default=[], help="Audit only clone names matching this glob")
    args = parser.parse_args()
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
