import pytest

from pages.home_page import HomePage
from pages.admin_page import AdminPage
from pages.booking_page import BookingPage


@pytest.fixture(scope="session")
def base_url():
    return "https://automationintesting.online"


@pytest.fixture(scope="session")
def api_base_url():
    return "https://automationintesting.online/api"


@pytest.fixture
def home_page(page, base_url):
    return HomePage(page, base_url)


@pytest.fixture
def admin_page(page, base_url):
    return AdminPage(page, base_url)


@pytest.fixture
def booking_page(page, base_url):
    return BookingPage(page, base_url)
