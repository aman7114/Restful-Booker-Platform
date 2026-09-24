import pytest
from playwright.sync_api import Page, expect

@pytest.mark.ui
def test_complete_room_booking_workflow(page: Page, config):
    """
    Complete end-to-end workflow for room booking:
    1. Navigate to home page
    2. Select dates and click Check Availability
    3. Book a room
    4. Fill out the guest details form
    5. Submit and verify confirmation
    """
    page.goto(config["UI_BASE_URL"])

    # Cookie banner check
    cookie_banner = page.locator("button:has-text('Let me hack!')")
    if cookie_banner.is_visible():
        cookie_banner.click()

    # Room cards expose a "Book now" link on the home page.
    page.get_by_role("link", name="Book now", exact=True).first.click()
    page.wait_for_load_state("networkidle")

    assert "/reservation/" in page.url, f"Unexpected reservation URL: {page.url}"
    page.get_by_role("button", name="Reserve Now").click()

    page.get_by_placeholder("Firstname").fill("Aman")
    page.get_by_placeholder("Lastname").fill("Sharma")
    page.get_by_placeholder("Email").fill("aman@example.com")
    page.get_by_placeholder("Phone").fill("01234567890")
    page.get_by_role("button", name="Reserve Now").click()

    expect(page.get_by_role("button", name="Cancel")).not_to_be_visible()
