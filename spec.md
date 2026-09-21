# Test Spec: Restful-Booker-Platform (RBP)

## Gemini configuration
# Put your own Gemini API key between the quotes before running generate_tests.py.
# Do NOT commit this file to GitHub while it contains a real key.
GEMINI_API_KEY = "YOUR_GEMINI_API_KEY"

## Target
- UI base URL: https://automationintesting.online
- API base URL: https://automationintesting.online/api
- The deployed demo is shared and resets its seeded data periodically.
- Admin credentials for this demo: username `admin`, password `password`.
- UI admin page: https://automationintesting.online/#/admin

## Workflow
1. generate_tests.py reads this file.
2. Gemini uses the Playwright MCP server only to explore the real UI.
3. Gemini uses the local `call_api` tool to inspect the real API responses.
4. Gemini generates a small pytest + Playwright + requests project.
5. The generated project is written under the `generated/` folder.
6. After generation, run the generated project with normal pytest. MCP is NOT needed for test execution.

## Test scope

### UI tests
Keep the UI suite small:
1. Admin login with valid credentials.
2. Admin login with invalid credentials.
3. Browse rooms on the home page and assert that room content is visible.
4. Open one room, choose a valid check-in/check-out date range, enter guest details, and submit a booking.
5. Negative booking case: leave one required guest field empty and verify the booking is not successfully submitted.

Do not add extra UI flows.

### API tests
Use Python `requests` only.

Cover:
1. POST `/auth/login`
   - positive login
   - negative login
2. GET `/room/`
   - verify status code and that the response contains room data
3. POST `/booking/`
   - create one booking using realistic test data
   - verify status code and response schema
4. GET `/booking/{id}`
   - use the booking ID returned by the create-booking test
   - verify status code and important response keys

Important:
- The API paths are under `/api`.
- Do not hardcode an authentication token.
- Obtain a token dynamically from `/auth/login` when an authenticated API call requires it.
- Use the token through a pytest fixture if needed.
- Do not create a large data set or run loops against the public demo.

## Page Object Model
Create simple page objects under `pages/`:

- `pages/base_page.py`
  - shared actions only: navigate, click, fill, wait, get_text
- `pages/home_page.py`
  - home page / room browsing
- `pages/admin_page.py`
  - admin login
- `pages/booking_page.py`
  - room booking widget and guest booking form

Rules:
- Every page object inherits from `BasePage`.
- Prefer `data-testid`, then accessible role/name, then CSS.
- Never use XPath.
- Test files must call page-object methods instead of raw locators.
- Keep locators inside page objects.
- Do not create unnecessary page classes.

## Test framework
- Python
- pytest
- pytest-playwright
- requests
- Playwright Python
- No Selenium.
- No unittest.
- No Jenkins.
- No Allure.
- No database.
- No Docker.
- No extra frameworks.

## Fixtures
Create `conftest.py` with:
- Playwright browser/page fixture support from pytest-playwright.
- `base_url`
- `api_base_url`
- `auth_token` fixture that calls `/auth/login` and returns the token.
- Keep fixtures small and readable.

## Assertions
- Every UI test must contain at least one meaningful assertion.
- Every API test must check the HTTP status code and relevant response body keys/schema.
- Negative tests must verify the expected failure/validation behavior.
- Avoid brittle assertions on full page text or exact dynamic counts.

## Generated project structure
The generator must create exactly these files:

### FILE: pages/base_page.py
```python
<code>
```

### FILE: pages/home_page.py
```python
<code>
```

### FILE: pages/admin_page.py
```python
<code>
```

### FILE: pages/booking_page.py
```python
<code>
```

### FILE: tests/ui/test_admin_login.py
```python
<code>
```

### FILE: tests/ui/test_booking.py
```python
<code>
```

### FILE: tests/api/test_auth_api.py
```python
<code>
```

### FILE: tests/api/test_rooms_api.py
```python
<code>
```

### FILE: tests/api/test_booking_api.py
```python
<code>
```

### FILE: conftest.py
```python
<code>
```

### FILE: requirements.txt
```text
<dependencies>
```

## Important generation rules
- First explore the real site with Playwright MCP.
- Use accessibility snapshots and real element names/roles where possible.
- Inspect the admin login page and one room booking flow.
- Use `call_api` to confirm the real request/response shapes for:
  - POST `https://automationintesting.online/api/auth/login`
  - GET `https://automationintesting.online/api/room/`
  - POST `https://automationintesting.online/api/booking/`
  - GET `https://automationintesting.online/api/booking/{id}`
- Do not guess selectors when the real site can be inspected.
- Keep the generated code straightforward enough for a beginner/intermediate QA automation project.
- Do not add features that are not requested above.
- Do not include markdown explanations outside the `### FILE:` blocks.
- Each file must be complete and directly runnable.
