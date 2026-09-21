# Restful-Booker-Platform — AI-Generated QA Suite

This project uses **Gemini** + the **Playwright MCP server** to explore the live [Restful-Booker-Platform](https://automationintesting.online) demo (UI and API), then automatically generates a small, runnable **pytest + Playwright + requests** test project from a single spec file (`spec.md`).

Instead of hand-writing selectors and test code, `generate_tests.py`:
1. Drives a real headless browser (via Playwright MCP) to observe the actual DOM of the homepage and admin login page.
2. Calls the real API (`/api/auth/login`, `/api/room/`, `/api/booking/`) to confirm real request/response shapes.
3. Sends this evidence — plus an explicit allowlist of *only the CSS selectors it actually observed* — to Gemini, which generates the Page Object Model, tests, and fixtures.
4. Locks the UI-facing selectors and a few runtime-sensitive files (fixtures, dynamic date/room logic) to deterministic, evidence-backed code rather than trusting the LLM's guesses.
5. Validates the final output and refuses to write the project if any selector wasn't actually observed on the live site.

The generated, ready-to-run project is written to `generated/`.

---

## Project Structure

```
.
├── spec.md                     # The single source of truth: target URLs, scope, rules, output file list
├── generate_tests.py            # Orchestrator: MCP exploration + API probing + Gemini generation + validation
├── generated/                   # Output: the runnable pytest project (created by generate_tests.py)
│   ├── conftest.py               # base_url / api_base_url / page-object fixtures
│   ├── requirements.txt
│   ├── pages/
│   │   ├── base_page.py          # Shared navigate/click/fill/wait helpers
│   │   ├── home_page.py          # Home page / room browsing
│   │   ├── admin_page.py         # Admin login
│   │   └── booking_page.py       # Booking / contact form widget
│   └── tests/
│       ├── ui/
│       │   ├── test_admin_login.py
│       │   └── test_booking.py
│       └── api/
│           ├── test_auth_api.py
│           ├── test_rooms_api.py
│           └── test_booking_api.py
├── reporting/
│   └── artifacts/                # Execution reports (JSON/Markdown/JUnit XML/log) from the last test run
└── .playwright-mcp/               # Debug artifacts (page snapshots, console logs) from MCP exploration runs
```

---

## How It Works

### 1. `spec.md` — the spec
Defines everything the generator needs:
- Target UI and API base URLs (`https://automationintesting.online`, `.../api`)
- Admin demo credentials
- Exact UI and API test scope (what to cover, what *not* to add)
- Page Object Model rules (no XPath, prefer `data-testid` → role/name → CSS, tests must call page objects rather than raw locators)
- Allowed frameworks (pytest, pytest-playwright, requests, Playwright Python — no Selenium/unittest/Jenkins/Allure/Docker/DB)
- The exact list of files the generator must produce

You can edit `spec.md` to change scope, target environment, or rules, then re-run the generator.

### 2. `generate_tests.py` — the generator
Run this to (re)generate the `generated/` project:

```bash
python generate_tests.py
```

What it does, in order:
1. **Reads `spec.md`** and extracts your Gemini API key from it.
2. **Starts a Playwright MCP server** (`npx @playwright/mcp@latest --headless`) and uses it to:
   - Load the homepage and admin login page of the live demo.
   - Evaluate the DOM to collect every unique, real CSS selector for interactive controls (inputs, buttons, links).
   - Try several known admin route variants (`/#/admin/`, `/#/admin`, `/admin/`, `/admin`) until one actually renders the login form.
3. **Calls the real API** directly (login, get rooms, create booking, get booking, a negative booking case) to capture real request/response shapes — this does **not** use Gemini quota.
4. **Builds a selector allowlist** from only what was actually observed, and sends one single Gemini request containing the spec, the browser/API evidence, and a hard "never invent a selector" contract.
5. **Parses Gemini's `### FILE:` blocks** and writes them under `generated/`.
6. **Overwrites the UI-facing files** (`pages/*.py`, `conftest.py`, `tests/ui/*.py`, `tests/api/test_auth_api.py`, `tests/api/test_booking_api.py`) with deterministic, template-based code built directly from the observed evidence — this avoids relying on the LLM for anything selector- or state-sensitive.
7. **Validates the result**: fails loudly if a UI test file contains raw Playwright calls (locators must live in page objects only), or if any selector in the page objects wasn't in the observed allowlist.

This script makes **exactly one** Gemini API call per run (quota-safe), using model `gemini-3.1-flash-lite`.

### 3. `generated/` — the runnable test project
A self-contained pytest project you can run independently of the generator (no MCP or Gemini needed to execute tests).

---

## Prerequisites

- Python 3.10+
- Node.js + npx (only needed to run the *generator*, for the Playwright MCP server)
- A Gemini API key (only needed to run the *generator*)

---

## Setup

### 1. Install dependencies for the generator
```bash
pip install requests google-genai mcp
```

### 2. Install dependencies for the generated test project
```bash
cd generated
pip install -r requirements.txt
playwright install chromium
```

### 3. Add your Gemini API key
Open `spec.md` and replace the placeholder:
```
GEMINI_API_KEY = "YOUR_GEMINI_API_KEY"
```
with your real key. **Do not commit `spec.md` with a real key in it.**

---

## Usage

### Generate (or regenerate) the test project
From the project root:
```bash
python generate_tests.py
```
This populates/overwrites everything under `generated/`.

### Run the generated tests
```bash
cd generated
pytest
```

Run only the API suite:
```bash
pytest tests/api
```

Run only the UI suite (headless by default via pytest-playwright):
```bash
pytest tests/ui
```

Run headed, to watch the browser:
```bash
pytest tests/ui --headed
```

---

## Test Coverage

### UI tests (`generated/tests/ui/`)
| Test | What it checks |
|---|---|
| `test_admin_login_success` | Admin login with valid credentials succeeds |
| `test_admin_login_failure` | Admin login with invalid credentials fails |
| `test_browse_rooms` | Homepage loads and room content is reachable |
| `test_negative_contact_booking` | Submitting the booking/contact form with required fields empty does not silently succeed |

### API tests (`generated/tests/api/`)
| Test | What it checks |
|---|---|
| `test_login_success` / `test_login_negative` | `POST /api/auth/login` returns a token on valid credentials, `401` on invalid |
| `test_get_rooms` | `GET /api/room/` returns `200` and room data |
| `test_create_and_get_booking` | `POST /api/booking/` creates a booking against a real room and future dates (retrying across rooms/dates to avoid conflicts on the shared demo), then `GET /api/booking/{id}` returns matching data |

Authentication tokens are never hardcoded — the `auth_token`/session flow fetches a fresh token from `/auth/login` at test time via fixtures/helpers.

---

## Design Decisions Worth Knowing

- **No hallucinated selectors.** Every CSS selector in `pages/*.py` is copied verbatim from a live DOM evaluation of the real site; the generator's validation step will raise an error and refuse to proceed if it detects a selector that wasn't actually observed.
- **Strict Page Object Model.** UI test files must not contain any `page.*`, `locator(...)`, or other Playwright calls — only page-object fixtures and assertions. This is enforced by static checks after generation.
- **Deterministic over generative where it matters.** Fixtures, selector-bearing page objects, and the dynamic room/date booking logic are written by the script itself (not the LLM) once Gemini's other output is in, since these are the pieces most sensitive to correctness and quota cost.
- **Single Gemini call per run.** The generator is designed to be quota-safe: exactly one `generate_content` request is made, with a hard stop before it if no real selectors were captured.
- **No fixed test data.** Because the deployed demo is shared and periodically reset, the booking test searches across rooms and a rolling window of future dates instead of hardcoding a room ID or date range.

---

## Reporting

`reporting/artifacts/` holds output from prior test runs:
- `execution.log` — raw pytest run log
- `execution.json` — structured execution summary
- `pytest-results.xml` — JUnit XML
- `ai-qa-report.md` / `ai-qa-report.json` — a human-readable summary (pass/fail counts, duration, observations)

These are regenerated by your own test-running/reporting workflow (not by `generate_tests.py` itself).

---

## Notes & Limitations

- The target site (`https://automationintesting.online`) is a public demo shared by many users; it resets its seeded data periodically, so booking tests are written to be resilient to conflicts rather than assuming fixed IDs.
- `.playwright-mcp/` contains raw MCP debug output (page snapshots, console logs) from exploration runs — useful for troubleshooting selector issues, safe to delete/ignore otherwise.
- `generated/.pytest_cache/` and `__pycache__/` directories are build artifacts, not source — see `.gitignore`.
- Never commit `spec.md` with a real `GEMINI_API_KEY` value.
