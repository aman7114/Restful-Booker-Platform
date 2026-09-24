import pytest
from playwright.sync_api import Page, expect
from pages.home_page import HomePage


@pytest.mark.ui
def test_discover_navigation_links(page: Page, config):
    """Navigation links exist."""
    hp = HomePage(page)
    hp.navigate(config["UI_BASE_URL"])
    hp.wait_for_load()
    count = hp.get_navigation_links().count()
    assert count > 0, f"Expected nav links, found {count}"


@pytest.mark.ui
def test_navigation_links_are_clickable(page: Page, config):
    """Admin link is functional."""
    hp = HomePage(page)
    hp.navigate(config["UI_BASE_URL"])
    hp.wait_for_load()
    links = hp.get_navigation_links()
    assert links.count() > 0

    for i in range(links.count()):
        link = links.nth(i)
        href = link.get_attribute("href") or ""
        text = (link.text_content() or "").strip()
        expect(link).to_be_enabled()

        if "admin" in href.lower() or text == "Admin":
            link.click()
            page.wait_for_load_state("networkidle")
            # Admin may show login page (/admin) or dashboard (/admin/rooms)
            assert "/admin" in page.url, f"Expected /admin in URL, got: {page.url}"
            # Navigate back explicitly (go_back() lands on about:blank for fresh pages)
            hp.navigate(config["UI_BASE_URL"])
            hp.wait_for_load()
            break
