import tempfile
import unittest
from pathlib import Path

from stealth_clone import AssetCapture, url_to_asset_path


class AssetPathTests(unittest.TestCase):
    def test_non_query_asset_path_is_unchanged(self):
        self.assertEqual(
            url_to_asset_path("https://example.com/assets/app.js"),
            Path("assets/app.js"),
        )

    def test_query_assets_do_not_collide(self):
        first = url_to_asset_path("https://example.com/assets/app.js?v=1")
        second = url_to_asset_path("https://example.com/assets/app.js?v=2")

        self.assertNotEqual(first, second)
        self.assertEqual(first.parent, Path("assets"))
        self.assertEqual(first.suffix, ".js")

    def test_next_image_optimizer_preserves_source_extension(self):
        rel = url_to_asset_path(
            "https://example.com/_next/image?"
            "url=https%3A%2F%2Fexample.com%2Fmedia%2Fhero.jpg&w=1920&q=75"
        )

        self.assertEqual(rel.parent, Path("_next/image"))
        self.assertEqual(rel.suffix, ".jpg")
        self.assertTrue(rel.name.startswith("__q_"))

    def test_query_path_remains_inside_output_tree(self):
        rel = url_to_asset_path(
            "https://example.com/assets/%2e%2e/secret.js?"
            "url=..%2F..%2Fetc%2Fpasswd&w=1"
        )

        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp).resolve()
            out_path = (out_dir / rel).resolve()
            out_path.relative_to(out_dir)


class AssetRewriteTests(unittest.TestCase):
    def test_prepare_html_rewrites_captured_query_asset(self):
        page_url = "https://example.com/"
        asset_url = (
            "https://example.com/_next/image?"
            "url=https%3A%2F%2Fexample.com%2Fmedia%2Fhero.jpg&w=1920&q=75"
        )
        rel = url_to_asset_path(asset_url)

        with tempfile.TemporaryDirectory() as tmp:
            capture = AssetCapture(Path(tmp), "example.com", "https", 443)
            capture.save_bytes(asset_url, rel, Path(tmp) / rel, b"image", "image/jpeg")
            html = (
                '<html><body><img src="/_next/image?'
                'url=https%3A%2F%2Fexample.com%2Fmedia%2Fhero.jpg&amp;w=1920&amp;q=75">'
                "</body></html>"
            )

            rewritten = capture.prepare_html(html, page_url)

        self.assertIn(f'src="/{rel.as_posix()}"', rewritten)
        self.assertNotIn("/_next/image?", rewritten)

    def test_prepare_html_keeps_uncaptured_same_origin_url_root_relative(self):
        capture = AssetCapture(Path("."), "example.com", "https", 443)
        rewritten = capture.prepare_html(
            '<link href="https://example.com/assets/site.css">',
            "https://example.com/",
        )

        self.assertEqual(rewritten, '<link href="/assets/site.css">')


if __name__ == "__main__":
    unittest.main()
