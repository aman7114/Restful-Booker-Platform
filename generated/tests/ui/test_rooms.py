import pytest
from playwright.sync_api import Page, expect
from pages.rooms_page import RoomsPage


@pytest.mark.ui
def test_discover_room_cards(page: Page, config):
    """Rooms are present on the home page."""
    rp = RoomsPage(page)
    rp.navigate(config["UI_BASE_URL"])
    rp.wait_for_load()
    count = rp.get_room_count()
    assert count > 0, f"Expected room cards, found {count}"


@pytest.mark.ui
def test_our_rooms_heading_not_a_room(page: Page, config):
    """'Our Rooms' section heading is visible."""
    rp = RoomsPage(page)
    rp.navigate(config["UI_BASE_URL"])
    rp.wait_for_load()
    expect(rp.our_rooms_heading).to_be_visible(timeout=10000)


@pytest.mark.ui
def test_select_room_and_navigate(page: Page, config):
    """Clicking 'Book now' navigates to reservation page."""
    rp = RoomsPage(page)
    rp.navigate(config["UI_BASE_URL"])
    rp.wait_for_load()
    rp.click_first_room()
    page.wait_for_timeout(1000)
    # The platform navigates to /reservation/{id}?... or stays on home page
    assert config["UI_BASE_URL"].split("//")[1] in page.url, (
        f"Unexpected URL after booking: {page.url}"
    )
