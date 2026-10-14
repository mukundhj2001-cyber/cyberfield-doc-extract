"""Browser smoke test: load samples, fix a failing invoice in the review screen, approve, export."""
import pytest
from playwright.sync_api import sync_playwright, expect


@pytest.mark.e2e
def test_smoke(live_server):
    with sync_playwright() as p:
        b = p.chromium.launch()
        page = b.new_page(accept_downloads=True)
        page.goto(live_server)
        page.get_by_test_id("load-samples").click()
        expect(page.get_by_test_id("doc-table")).to_contain_text("invoice_harbor_supplies_mismatch.pdf", timeout=60000)
        page.get_by_text("invoice_harbor_supplies_mismatch.pdf").click()
        expect(page.get_by_test_id("validation")).to_contain_text("vs total 18,999.00")
        page.get_by_test_id("field-total").fill("19809.84")
        page.get_by_test_id("approve").click()
        expect(page.get_by_test_id("doc-status")).to_have_text("approved")
        page.goto(live_server + "/#/")
        with page.expect_download() as dl:
            page.get_by_test_id("export-csv").click()
        assert "HOS/26/0931" in open(dl.value.path(), encoding="utf-8").read()
        b.close()
