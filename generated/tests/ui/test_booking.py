import pytest
from playwright.sync_api import Page, expect
from pages.booking_page import BookingPage
import uuid
import random


@pytest.mark.ui
def test_reservation_page_loads(page: Page, config):
    """Home page loads with Check Availability section."""
    bp = BookingPage(page)
    bp.navigate(config["UI_BASE_URL"])
    bp.wait_for_load()
    assert bp.is_page_loaded()


@pytest.mark.ui
def test_calendar_controls_present(page: Page, config):
    """Check Availability button is present."""
    bp = BookingPage(page)
    bp.navigate(config["UI_BASE_URL"])
    bp.wait_for_load()
    assert bp.calendar_controls_present()


@pytest.mark.ui
def test_booking_form_fields_present(page: Page, config):
    """Contact form fields are present on the home page."""
    bp = BookingPage(page)
    bp.navigate(config["UI_BASE_URL"])
    bp.wait_for_load()
    assert bp.booking_form_fields_present()


@pytest.mark.ui
def test_submit_booking(page: Page, config):
    """Contact form submits successfully."""
    bp = BookingPage(page)
    bp.navigate(config["UI_BASE_URL"])
    bp.wait_for_load()

    name = f"UI {uuid.uuid4().hex[:6]}"
    email = f"ui{uuid.uuid4().hex[:6]}@example.com"
    # Phone: 11 digits (platform validates 11-21)
    phone = f"0{random.randint(1000000000, 9999999999)}"
    # Subject >= 5 chars, Message >= 20 chars (server-side validation)
    subject = "Test Booking Inquiry"
    message = "This is an automated test message for the contact form submission."

    bp.fill_and_submit(name, email, phone, subject, message)
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(2000)
    # Platform shows a "Thanks for getting in touch..." heading on success
    expect(bp.success_heading).to_be_visible(timeout=10000)
