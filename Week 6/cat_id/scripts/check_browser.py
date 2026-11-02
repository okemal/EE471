"""Exercise the real local website in an isolated Chromium browser.

Run with a ready server: uv run python scripts/check_browser.py
Screenshots and JSON observations go to ignored artifacts/, never to source.
"""

import json
import os
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
BASE = os.getenv("CAT_ID_TEST_URL", "http://127.0.0.1:8000")
OUT = Path(os.getenv("CAT_ID_ARTIFACT_DIR", str(ROOT / "artifacts")))
OUT.mkdir(parents=True, exist_ok=True)


def main():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 1000})
        errors = []
        external_requests = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.on(
            "request",
            lambda request: (
                external_requests.append(request.url)
                if not request.url.startswith(BASE) and not request.url.startswith("blob:")
                else None
            ),
        )
        page.goto(BASE, wait_until="networkidle")
        expect(page.locator("#featured-species .species-card")).to_have_count(4)
        expect(page.locator("#model-status")).to_contain_text("ready")
        page.screenshot(path=str(OUT / "home-desktop.png"), full_page=True)

        # A genuine file upload and real inference, including the download action.
        page.locator("#image-input").set_input_files(ROOT / "frontend/assets/domestic-cat.jpg")
        expect(page.locator("#identify-button")).to_be_enabled()
        page.locator("#identify-button").click()
        expect(page.locator("#analysis-title")).to_have_text("Domestic cat", timeout=180000)
        expect(page.locator(".score-note")).to_contain_text("not probabilities")
        page.screenshot(path=str(OUT / "result-desktop.png"), full_page=True)
        with page.expect_download() as download:
            page.locator("#save-result").click()
        record_path = OUT / "downloaded-observation.json"
        download.value.save_as(record_path)
        record = json.loads(record_path.read_text())
        assert record["candidates"][0]["species"]["scientific_name"] == "Felis catus"
        assert "image" not in record
        page.get_by_role("button", name="Meet this species").click()
        expect(page.locator("#detail-dialog")).to_be_visible()
        expect(page.locator("#dialog-title")).to_have_text("Domestic cat")
        page.keyboard.press("Escape")
        expect(page.locator("#detail-dialog")).not_to_be_visible()

        # A non-cat is rejected, without displaying a spurious species suggestion.
        page.locator("#start-over").click()
        page.locator('[data-example="dog"]').click()
        expect(page.locator("#identify-button")).to_be_enabled()
        page.locator("#identify-button").click()
        expect(page.locator(".result-tag")).to_have_text("↳  No reliable match", timeout=180000)
        expect(page.locator(".candidate")).to_have_count(0)
        page.screenshot(path=str(OUT / "no-match.png"), full_page=True)
        page.locator("#start-over").click()

        # Validation happens before sending an upload.
        page.locator("#image-input").set_input_files(
            {"name": "unsafe.svg", "mimeType": "image/svg+xml", "buffer": b"<svg/>"}
        )
        expect(page.locator("#upload-error")).to_contain_text("JPEG, PNG, or WebP")
        page.locator("#image-input").set_input_files(
            {
                "name": "too-large.jpg",
                "mimeType": "image/jpeg",
                "buffer": b"x" * (10 * 1024 * 1024 + 1),
            }
        )
        expect(page.locator("#upload-error")).to_contain_text("too large")

        # Search, filters, empty state, and a native keyboard-dismissable dialog.
        page.get_by_role("link", name="Field guide", exact=True).click()
        expect(page.locator("#species-grid .species-card")).to_have_count(41)
        page.locator("#species-search").fill("panthera")
        expect(page.locator("#species-grid .species-card")).to_have_count(5)
        page.locator("#subfamily-filter").select_option("Felinae")
        expect(page.locator("#empty-search")).to_be_visible()
        page.locator("#species-search").fill("")
        expect(page.locator("#species-grid .species-card")).to_have_count(34)
        page.locator("#subfamily-filter").select_option("Pantherinae")
        expect(page.locator("#species-grid .species-card")).to_have_count(7)
        page.screenshot(path=str(OUT / "field-guide.png"), full_page=True)
        page.locator('[data-open="taxonomy"]').click()
        expect(page.locator("#dialog-title")).to_have_text("Names evolve, too.")
        page.keyboard.press("Escape")

        # Explicitly simulated uncertainty exercises rendering, not claimed model accuracy.
        page.get_by_role("link", name="Identify", exact=True).click()
        uncertain = {
            **record,
            "status": "uncertain",
            "message": "This looks like a cat, but the species is not clear enough to identify.",
        }
        page.route("**/api/identify", lambda route: route.fulfill(json=uncertain))
        page.locator('[data-example="tiger"]').click()
        expect(page.locator("#identify-button")).to_be_enabled()
        page.locator("#identify-button").click()
        expect(page.locator("#analysis-title")).to_have_text("A cat. But which one?")
        expect(page.locator(".candidate")).to_have_count(3)
        page.screenshot(path=str(OUT / "uncertain-state.png"), full_page=True)
        page.unroute("**/api/identify")
        page.locator("#start-over").click()

        # A real lookalike sample, when the optional evaluation photos are cached.
        ambiguous = ROOT / ".cache/evaluation/caracal.jpg"
        if ambiguous.exists():
            page.locator("#image-input").set_input_files(ambiguous)
            expect(page.locator("#identify-button")).to_be_enabled()
            page.locator("#identify-button").click()
            expect(page.locator("#analysis-title")).to_have_text(
                "A cat. But which one?", timeout=180000
            )
            page.screenshot(path=str(OUT / "uncertain-real.png"), full_page=True)
            page.locator("#start-over").click()

        # Responsive layouts and a real mobile upload.
        for width in (320, 390, 768, 1024):
            page.set_viewport_size({"width": width, "height": 844})
            assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth"), (
                f"Horizontal overflow at {width}px"
            )
        page.set_viewport_size({"width": 390, "height": 844})
        page.screenshot(path=str(OUT / "home-mobile.png"), full_page=True)
        page.locator('[data-example="tiger"]').click()
        expect(page.locator("#identify-button")).to_be_enabled()
        page.locator("#identify-button").click()
        expect(page.locator("#analysis-title")).to_have_text("Tiger", timeout=180000)
        assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
        page.screenshot(path=str(OUT / "result-mobile.png"), full_page=True)
        page.get_by_role("button", name="Sources & photo credits").click()
        expect(page.locator(".credit-item")).to_have_count(6)
        page.keyboard.press("Escape")
        assert errors == [], errors
        assert external_requests == [], external_requests
        browser.close()
        print(
            "Browser checks passed: real uploads, matched/no-match states, simulated uncertainty, downloads, search, validation, dialogs, four responsive widths, and no external browser requests."
        )


if __name__ == "__main__":
    main()
