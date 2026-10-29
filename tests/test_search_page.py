"""Tests for generated catalog search assets."""

from importlib import resources
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from kev_dashboard.search import render_search_page


class SearchPageTests(unittest.TestCase):
    def test_render_writes_complete_page_and_packaged_script(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            output_dir = Path(temporary_directory) / "release"
            page_path, script_path = render_search_page(output_dir)

            self.assertEqual(page_path, output_dir / "search.html")
            self.assertEqual(script_path, output_dir / "search.js")

            page = page_path.read_text(encoding="utf-8")
            script = script_path.read_text(encoding="utf-8")

        packaged_script = (
            resources.files("kev_dashboard")
            .joinpath("static/search.js")
            .read_text(encoding="utf-8")
        )

        self.assertTrue(page.startswith("<!doctype html>"))
        self.assertTrue(page.endswith("</html>\n"))
        self.assertIn("<title>Search CISA KEV Catalog</title>", page)
        self.assertIn('<script src="search.js" defer></script>', page)
        self.assertIn('href="index.html"', page)
        self.assertIn(
            '<a href="data/vulnerabilities.csv" download>', page
        )
        self.assertIn("all entries, regardless of filters", page)
        self.assertLess(
            page.index("</fieldset>"),
            page.index('<a href="data/vulnerabilities.csv" download>'),
        )
        self.assertIn("connect-src 'self'", page)
        self.assertEqual(script, packaged_script)
        self.assertIn('data/kev_snapshot.json', script)


if __name__ == "__main__":
    unittest.main()
