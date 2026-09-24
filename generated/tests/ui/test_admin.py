import pytest
from playwright.sync_api import Page, expect
from pages.admin_page import AdminPage


@pytest.mark.ui
def test_admin_page_loads(page: Page, config):
    """Admin login page loads correctly."""
    ap = AdminPage(page)
    ap.navigate_to_admin(config["UI_BASE_URL"], config["ADMIN_PATH"])
    ap.wait_for_load()
    # Ensure we're on the login page (log out if already in)
    ap.ensure_logged_out()
    expect(ap.username_input).to_be_visible()
    expect(ap.password_input).to_be_visible()
    expect(ap.login_button).to_be_visible()


@pytest.mark.ui
def test_admin_login_positive(page: Page, config):
    """Login with valid credentials shows the dashboard."""
    ap = AdminPage(page)
    ap.navigate_to_admin(config["UI_BASE_URL"], config["ADMIN_PATH"])
    ap.wait_for_load()
    ap.ensure_logged_out()
    ap.login(config["ADMIN_USERNAME"], config["ADMIN_PASSWORD"])
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(1000)
    assert ap.is_logged_in(), "Admin login with valid credentials failed."


@pytest.mark.ui
def test_admin_login_negative(page: Page, config):
    """Login with invalid credentials shows error alert."""
    ap = AdminPage(page)
    ap.navigate_to_admin(config["UI_BASE_URL"], config["ADMIN_PATH"])

    # dismiss cookie banner if present so login button is not obscured
    cookie_banner = page.locator("button:has-text('Let me hack!')")
    if cookie_banner.is_visible():
        cookie_banner.click()

    ap.login("invalid_user", "wrong_password")

    # Wait for the error alert
    error_alert = page.get_by_role("alert").filter(has_text="Invalid")
    expect(error_alert).to_be_visible(timeout=5000)
