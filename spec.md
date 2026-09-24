# Master Specification — AI QA Automation Contract
# Restful Booker Platform

## PURPOSE

This document is the master contract given to the Gemini AI for test
generation. The AI must generate executable test automation code
STRICTLY based on:

1. This specification (spec.md)
2. The UI specification (ui.md)
3. The API specification (api.md)
4. Collected UI evidence (accessibility snapshots, screenshots, discovered elements)
5. Collected API evidence (actual API responses, endpoint behavior)

The AI must NOT:
- Invent selectors that do not appear in the evidence
- Invent endpoints not documented in api.md
- Assume application behavior not observed in evidence
- Hardcode credentials, URLs, or model names
- Hardcode booking IDs, room IDs, or dynamic values
- Use fixed dates — all dates must be runtime-calculated

---

## TECHNOLOGY STACK

| Component | Technology |
|-----------|-----------|
| UI Automation | Playwright + pytest-playwright |
| API Tests | requests + pytest |
| Test Framework | pytest |
| Test Reports | pytest-html (HTML), junit.xml, execution.json |
| Page Model | Page Object Model (POM) |
| Configuration | python-dotenv (.env file) |

---

## OUTPUT STRUCTURE

The AI must generate a complete, immediately executable test project.

All output files must be returned in this JSON format:

```json
{
  "files": [
    {
      "path": "pages/base_page.py",
      "content": "..."
    }
  ]
}
```

Paths are relative to the `generated/` directory.

### Required Output Files

```
conftest.py                     # pytest fixtures
pytest.ini                      # pytest configuration
requirements.txt                # test project dependencies

pages/
  base_page.py                  # Base page with shared methods
  home_page.py                  # Home page POM
  rooms_page.py                 # Rooms/listing POM
  booking_page.py               # Reservation/booking POM
  admin_page.py                 # Admin login/dashboard POM

tests/
  ui/
    test_home.py                # Home page tests
    test_navigation.py          # Navigation tests
    test_rooms.py               # Room discovery and selection tests
    test_booking.py             # Booking/reservation tests
    test_admin.py               # Admin login tests
  api/
    test_auth.py                # Authentication API tests
    test_rooms_api.py           # Rooms API tests
    test_bookings_api.py        # Bookings CRUD + negative tests
```

---

## PAGE OBJECT MODEL REQUIREMENTS

### BasePage

```python
class BasePage:
    def __init__(self, page):
        self.page = page

    def navigate(self, url): ...
    def wait_for_load(self): ...
    def take_screenshot(self, name): ...
```

### HomePage

Responsible for:
- Verifying page load
- Accessing navigation
- Discovering rooms section

### RoomsPage

Responsible for:
- Discovering room cards from DOM
- Selecting a room
- Clicking booking action
- NOT treating "Our Rooms" heading as a room

### BookingPage

Responsible for:
- Date picker interaction
- Guest detail form filling
- Submitting booking
- Verifying confirmation

### AdminPage

Responsible for:
- Entering credentials (from config/fixtures, never hardcoded)
- Submitting login
- Verifying dashboard

### POM Rules

- Business actions as methods: `rooms_page.select_available_room()`
- No hardcoded MCP refs or dynamically-assigned IDs from the browser
- All locators derived from evidence (ARIA roles, accessible names, data-testid)
- No test assertions inside page classes

---

## UI TEST REQUIREMENTS

### test_home.py

- `test_home_page_loads` — Verify page title is non-empty and load succeeds
- `test_navigation_is_visible` — Verify navigation element is present
- `test_rooms_section_exists` — Verify rooms section is discoverable

### test_navigation.py

- `test_discover_navigation_links` — Discover nav links, verify count > 0
- `test_navigation_links_are_clickable` — Verify each discovered link is functional

### test_rooms.py

- `test_discover_room_cards` — Verify rooms are discovered dynamically
- `test_our_rooms_heading_not_a_room` — Assert "Our Rooms" text alone is not a room card
- `test_select_room_and_navigate` — Select a room, click Book Now, verify URL changes

### test_booking.py

- `test_reservation_page_loads` — Verify reservation page loads
- `test_calendar_controls_present` — Verify date picker exists
- `test_booking_form_fields_present` — Verify guest fields exist
- `test_submit_booking` — Fill and submit booking form with generated data

### test_admin.py

- `test_admin_page_loads` — Verify admin page loads
- `test_admin_login_positive` — Login with valid credentials from .env
- `test_admin_login_negative` — Login with invalid credentials, verify error

---

## API TEST REQUIREMENTS

### test_auth.py

- `test_login_valid_credentials` — POST /auth/login → 200 + token
- `test_login_invalid_password` — POST /auth/login → 403
- `test_login_empty_credentials` — POST /auth/login → 403

### test_rooms_api.py

- `test_get_all_rooms` — GET /room → 200 + non-empty rooms array
- `test_rooms_have_required_fields` — Validate roomid, roomName, type, roomPrice
- `test_get_single_room` — GET /room/{id} using discovered room ID → 200
- `test_get_invalid_room` — GET /room/99999 → 404 or 500

### test_bookings_api.py

- `test_create_booking` — POST /booking → 201 + bookingid
- `test_get_created_booking` — GET /booking/{id} → 200 + correct data
- `test_update_booking` — PUT /booking/{id} → 200
- `test_delete_booking` — DELETE /booking/{id} → 202/204
- `test_get_deleted_booking` — GET /booking/{id} after delete → 404
- `test_create_booking_missing_field` — POST without required field → 4xx
- `test_create_booking_no_auth` — POST /booking without token → 403
- `test_delete_without_auth` — DELETE /booking/{id} without token → 403

---

## FIXTURE REQUIREMENTS

### conftest.py must provide:

```python
@pytest.fixture(scope="session")
def config():
    """Load configuration from .env"""
    # Returns dict with UI_BASE_URL, API_BASE_URL, etc.

@pytest.fixture(scope="session")
def browser_context(playwright, config):
    """Playwright browser context"""

@pytest.fixture
def page(browser_context):
    """Fresh page per test"""

@pytest.fixture(scope="session")
def api_token(config):
    """Obtain and cache auth token"""

@pytest.fixture(scope="session")
def room_id(config):
    """Discover and cache a valid room ID"""

@pytest.fixture
def booking_payload(room_id):
    """Generate a fresh booking payload per test"""
```

---

## PYTEST CONFIGURATION

### pytest.ini

```ini
[pytest]
testpaths = tests
addopts = --html=reports/html/report.html --self-contained-html
          --junitxml=reports/junit.xml
markers =
    ui: UI tests
    api: API tests
```

---

## REPORTING REQUIREMENTS

### execution.json structure:

```json
{
  "total": 0,
  "passed": 0,
  "failed": 0,
  "skipped": 0,
  "errors": 0,
  "duration_seconds": 0.0,
  "tests": [
    {
      "name": "test_name",
      "status": "passed|failed|skipped|error",
      "duration_seconds": 0.0,
      "failure_message": null,
      "traceback": null
    }
  ]
}
```

---

## GENERATION RULES — CRITICAL

1. **Evidence-Only Selectors:** All selectors must come from UI evidence.
   Never invent role attributes, test IDs, or class names not seen in evidence.

2. **No Hardcoded Credentials:** All credentials come from pytest fixtures
   which load from .env via python-dotenv.

3. **No Hardcoded URLs:** Base URLs come from config fixture.

4. **Runtime Dates Only:** Use `datetime.date.today()` + offsets. Never
   write literal date strings.

5. **Runtime Data Only:** Guest names, emails, phones — generate with
   uuid/random, not fixed strings.

6. **No Fixed IDs:** Room IDs come from GET /room response.
   Booking IDs come from POST /booking response.

7. **POM Separation:** Page classes contain locators and actions only.
   Assertions belong in test functions only.

8. **Executable Code:** All generated code must be immediately runnable
   without modification. No placeholder comments like `# TODO: implement`.

9. **Meaningful Test Names:** Test function names must describe the behavior
   being verified.

10. **No Invented Workflows:** Do not generate tests for features not
    documented in ui.md, api.md, or observed in evidence.
