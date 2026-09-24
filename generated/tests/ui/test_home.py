import pytest
from playwright.sync_api import Page, expect
from pages.home_page import HomePage


@pytest.mark.ui
def test_home_page_loads(page: Page, config):
    """Home page loads with correct title."""
    hp = HomePage(page)
    hp.navigate(config["UI_BASE_URL"])
    hp.wait_for_load()
    assert hp.is_loaded()


@pytest.mark.ui
def test_navigation_is_visible(page: Page, config):
    """Nav bar is visible on home page."""
    hp = HomePage(page)
    hp.navigate(config["UI_BASE_URL"])
    hp.wait_for_load()
    assert hp.get_navigation_links().count() > 0


@pytest.mark.ui
def test_rooms_section_exists(page: Page, config):
    """Our Rooms heading is visible."""
    hp = HomePage(page)
    hp.navigate(config["UI_BASE_URL"])
    hp.wait_for_load()
    expect(hp.rooms_heading).to_be_visible(timeout=10000)
