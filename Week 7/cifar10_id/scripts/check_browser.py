"""End-to-end Playwright Chromium verification for Vision10 CIFAR-10 classifier."""

import json
import os
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
BASE = os.getenv("CIFAR10_ID_TEST_URL", "http://127.0.0.1:8001")
OUT = Path(os.getenv("CIFAR10_ID_ARTIFACT_DIR", str(ROOT / "artifacts")))
OUT.mkdir(parents=True, exist_ok=True)


def main() -> None:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 1000})
        errors: list[str] = []
        external_requests: list[str] = []
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
        expect(page.locator("#featured-classes .species-card")).to_have_count(4)
        expect(page.locator("#model-status")).to_contain_text("ready")
        page.screenshot(path=str(OUT / "home-desktop.png"), full_page=True)

        # Real upload via file input + side-by-side verification + JSON export.
        page.locator("#image-input").set_input_files(ROOT / "frontend/assets/airplane.png")
        expect(page.locator("#identify-button")).to_be_enabled()
        page.locator("#identify-button").click()
        expect(page.locator("#analysis-title")).to_have_text("Airplane", timeout=60_000)
        expect(page.locator("#comparison-panel")).to_be_visible()
        expect(page.locator(".baseline-card .model-title")).not_to_be_empty()
        expect(page.locator(".optimized-card .model-title")).to_have_text("Airplane")
        expect(page.locator(".prob-row")).to_have_count(6)
        page.screenshot(path=str(OUT / "result-airplane-desktop.png"), full_page=True)

        with page.expect_download() as download:
            page.locator("#save-result").click()
        record_path = OUT / "downloaded-comparison.json"
        download.value.save_as(record_path)
        record = json.loads(record_path.read_text(encoding="utf-8"))
        assert record["optimized"]["predicted_class"] == "plane"
        assert record["baseline"]["architecture"] == "TutorialCifarNet"
        assert record["optimized"]["architecture"] == "CifarResNet9"
        assert "image" not in record

        # Inspect class dialog and keyboard Escape close.
        page.get_by_role("button", name="Inspect class clues").click()
        expect(page.locator("#detail-dialog")).to_be_visible()
        expect(page.locator("#dialog-title")).to_have_text("Airplane")
        page.keyboard.press("Escape")
        expect(page.locator("#detail-dialog")).not_to_be_visible()

        # Test disagreement/challenging sample (cat) side-by-side comparison.
        page.locator("#start-over").click()
        page.locator('[data-example="cat"]').click()
        expect(page.locator("#identify-button")).to_be_enabled()
        page.locator("#identify-button").click()
        expect(page.locator("#analysis-title")).to_have_text("Cat", timeout=60_000)
        expect(page.locator(".comparison-verdict")).to_be_visible()
        page.screenshot(path=str(OUT / "result-cat-comparison.png"), full_page=True)
        page.locator("#start-over").click()

        # Upload validation before network call.
        page.locator("#image-input").set_input_files(
            {"name": "unsafe.svg", "mimeType": "image/svg+xml", "buffer": b"<svg/>"}
        )
        expect(page.locator("#upload-error")).to_contain_text("JPEG, PNG, or WebP")
        page.locator("#image-input").set_input_files(
            {
                "name": "too-large.png",
                "mimeType": "image/png",
                "buffer": b"x" * (10 * 1024 * 1024 + 1),
            }
        )
        expect(page.locator("#upload-error")).to_contain_text("too large")

        # Catalogue search and group filter.
        page.get_by_role("link", name="Class catalogue", exact=True).click()
        expect(page.locator("#classes-grid .species-card")).to_have_count(10)
        page.locator("#class-search").fill("truck")
        expect(page.locator("#classes-grid .species-card")).to_have_count(1)
        page.locator("#group-filter").select_option("Animals")
        expect(page.locator("#empty-search")).to_be_visible()
        page.locator("#class-search").fill("")
        expect(page.locator("#classes-grid .species-card")).to_have_count(6)
        page.locator("#group-filter").select_option("all")
        expect(page.locator("#classes-grid .species-card")).to_have_count(10)
        page.screenshot(path=str(OUT / "catalogue-desktop.png"), full_page=True)

        # HPO & Benchmarks page verification.
        page.locator('[data-nav="about"]').click()
        expect(page.locator("#benchmark-kpis .kpi-card")).to_have_count(4)
        expect(page.locator("#hpo-table-body tr")).to_have_count(5)
        expect(page.locator("#per-class-table-body tr")).to_have_count(10)
        page.screenshot(path=str(OUT / "benchmarks-desktop.png"), full_page=True)

        # Credits modal.
        page.get_by_role("button", name="Dataset & model credits").click()
        expect(page.locator(".credit-item")).to_have_count(2)
        page.keyboard.press("Escape")

        # Responsive checks across 320, 390, 768, 1024 px.
        page.locator('[data-nav="identify"]').click()
        for width in (320, 390, 768, 1024):
            page.set_viewport_size({"width": width, "height": 844})
            assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth"), (
                f"Horizontal overflow at {width}px"
            )
        page.set_viewport_size({"width": 390, "height": 844})
        page.screenshot(path=str(OUT / "home-mobile.png"), full_page=True)

        assert errors == [], errors
        assert external_requests == [], external_requests
        browser.close()
        print("Browser E2E checks passed with 0 page errors and 0 external requests.")


if __name__ == "__main__":
    main()
