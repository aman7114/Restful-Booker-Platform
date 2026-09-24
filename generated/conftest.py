import pytest
import requests
from pathlib import Path
from dotenv import load_dotenv
import os
import datetime
import uuid
import random

load_dotenv(Path(__file__).parent.parent / ".env")


@pytest.fixture(scope="session")
def config():
    return {
        "UI_BASE_URL": os.getenv("UI_BASE_URL", "https://automationintesting.online"),
        "API_BASE_URL": os.getenv("API_BASE_URL", "https://automationintesting.online/api"),
        "ADMIN_USERNAME": os.getenv("ADMIN_USERNAME", "admin"),
        "ADMIN_PASSWORD": os.getenv("ADMIN_PASSWORD", "password"),
        "ADMIN_PATH": os.getenv("ADMIN_PATH", "/admin"),
    }


@pytest.fixture(scope="function")
def browser_context(browser):
    context = browser.new_context()
    yield context
    context.close()


@pytest.fixture(scope="function")
def page(browser_context):
    page = browser_context.new_page()
    yield page
    page.close()


@pytest.fixture(scope="session")
def api_token(config):
    url = f"{config['API_BASE_URL']}/auth/login"
    r = requests.post(url, json={
        "username": config["ADMIN_USERNAME"],
        "password": config["ADMIN_PASSWORD"],
    })
    r.raise_for_status()
    token = r.json().get("token")
    assert token, "API token not found"
    return token


@pytest.fixture(scope="session")
def authenticated_api_session(api_token):
    s = requests.Session()
    s.cookies.set("token", api_token)
    yield s


@pytest.fixture(scope="session")
def room_id(config):
    r = requests.get(f"{config['API_BASE_URL']}/room")
    r.raise_for_status()
    rooms = r.json().get("rooms", [])
    assert rooms, "No rooms found"
    return rooms[0]["roomid"]


@pytest.fixture(scope="function")
def booking_payload(room_id):
    today = datetime.date.today()
    # Use 1000-1100 days ahead to minimise date-conflict 409 errors
    checkin = today + datetime.timedelta(days=random.randint(1000, 1100))
    checkout = checkin + datetime.timedelta(days=random.randint(1, 5))
    first = f"Test{uuid.uuid4().hex[:6]}"
    last = f"User{uuid.uuid4().hex[:6]}"
    # Phone: 11 digits exactly (platform validates 11-21)
    phone = f"0{random.randint(1000000000, 9999999999)}"
    return {
        "roomid": room_id,
        "firstname": first,
        "lastname": last,
        "depositpaid": True,
        "email": f"{first.lower()}@example.com",
        "phone": phone,
        "bookingdates": {
            "checkin": str(checkin),
            "checkout": str(checkout),
        },
    }

from pytest_report_hook import pytest_runtest_logreport, pytest_sessionfinish
