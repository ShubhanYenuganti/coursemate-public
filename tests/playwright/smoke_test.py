"""
Smoke test: start dev stack via DEV_BYPASS_AUTH, load the app, verify /dashboard.

Run from the project root:
    python tests/playwright/smoke_test.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from tests.playwright.dev_context import dev_app


def main():
    print("Starting CourseMate dev stack + Playwright...")
    with dev_app(headless=True) as page:
        url = page.url
        print(f"  URL:   {url}")
        print(f"  Title: {page.title()}")

        assert "/dashboard" in url, f"Expected /dashboard in URL, got: {url}"

        header = page.locator("header").first
        assert header.is_visible(), "Dashboard header not visible"

        brand = page.get_by_text("CourseMate", exact=True).first
        assert brand.is_visible(), "'CourseMate' brand text not visible in header"

        screenshot_path = Path(__file__).parent / "screenshot_smoke.png"
        page.screenshot(path=str(screenshot_path))
        print(f"  Screenshot: {screenshot_path}")

    print("PASS")


if __name__ == "__main__":
    main()
