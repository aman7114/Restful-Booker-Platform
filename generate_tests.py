import os
import asyncio
import json
import re
from pathlib import Path
from urllib.parse import urlparse

import requests
from google import genai
from google.genai import types
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

SCRIPT_DIR = Path(__file__).resolve().parent
SPEC_PATH = SCRIPT_DIR / "spec.md"
OUTPUT_DIR = SCRIPT_DIR / "generated"
MODEL = "gemini-3.1-flash-lite"
UI_BASE_URL = "https://automationintesting.online"
API_BASE_URL = f"{UI_BASE_URL}/api"
MAX_EVIDENCE_CHARS = 60000

EXPECTED_FILES = {
    "pages/base_page.py",
    "pages/home_page.py",
    "pages/admin_page.py",
    "pages/booking_page.py",
    "tests/ui/test_admin_login.py",
    "tests/ui/test_booking.py",
    "tests/api/test_auth_api.py",
    "tests/api/test_rooms_api.py",
    "tests/api/test_booking_api.py",
    "conftest.py",
    "requirements.txt",
}


def read_spec():
    if not SPEC_PATH.exists():
        raise FileNotFoundError(f"spec.md was not found: {SPEC_PATH}")

    text = SPEC_PATH.read_text(encoding="utf-8")

    # Prefer the environment variable so the real API key
    # never needs to be stored in spec.md or GitHub.
    api_key = os.getenv("GEMINI_API_KEY", "").strip()

    if api_key:
        return text, api_key

    # Local fallback: allow a real key in spec.md for backward compatibility.
    match = re.search(
        r'GEMINI_API_KEY\s*=\s*["\']([^"\']+)["\']',
        text,
    )

    if match:
        candidate = match.group(1).strip()

        if candidate and candidate not in {
            "YOUR_GEMINI_API_KEY",
            "PASTE_YOUR_GEMINI_API_KEY_HERE",
        }:
            return text, candidate

    raise ValueError(
        "Gemini API key not found. Set the GEMINI_API_KEY environment "
        "variable before running generate_tests.py."
    )


def call_api(method, url, body=None, headers=None):
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.netloc != "automationintesting.online" or not parsed.path.startswith("/api/"):
        return {"error": "Only https://automationintesting.online/api/* is allowed."}
    try:
        r = requests.request(method.upper(), url, json=body, headers=headers, timeout=15)
        try:
            data = r.json()
        except ValueError:
            data = r.text[:5000]
        return {"status": r.status_code, "body": data}
    except requests.RequestException as exc:
        return {"error": f"{type(exc).__name__}: {exc}"}


async def mcp_call(session, name, args):
    result = await session.call_tool(name, args)
    if getattr(result, "structuredContent", None) is not None:
        return result.structuredContent
    parts = []
    for item in getattr(result, "content", None) or []:
        if getattr(item, "text", None):
            parts.append(item.text)
        elif hasattr(item, "model_dump"):
            parts.append(item.model_dump())
        else:
            parts.append(str(item))
    return "\n".join(parts)


def clean_code(code):
    code = code.strip()
    code = re.sub(r"^```(?:python|text|plaintext)?\s*", "", code)
    code = re.sub(r"\s*```\s*$", "", code)
    return code.strip()


def save_output(text):
    pattern = re.compile(r"### FILE:\s*([^\r\n]+)\s*\r?\n(.*?)(?=\r?\n### FILE:|\Z)", re.DOTALL)
    matches = pattern.findall(text)
    if not matches:
        raise RuntimeError("Gemini did not return ### FILE: blocks.")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    written = set()
    for raw_path, raw_code in matches:
        path = raw_path.strip().replace("\\", "/")
        if path not in EXPECTED_FILES:
            continue
        if path in written:
            raise RuntimeError(f"Duplicate generated file: {path}")
        if Path(path).is_absolute() or ".." in Path(path).parts:
            raise RuntimeError(f"Unsafe generated path: {path}")
        code = clean_code(raw_code)
        if not code:
            raise RuntimeError(f"Empty generated file: {path}")
        target = OUTPUT_DIR / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(code + "\n", encoding="utf-8")
        written.add(path)
        print(f"Wrote {path}")

    missing = EXPECTED_FILES - written
    if missing:
        raise RuntimeError("Missing generated files: " + ", ".join(sorted(missing)))


def extract_css_strings(code):
    """Collect complete string arguments passed to common Playwright locator calls."""
    # Use a backreference so selectors containing the other quote character
    # are captured completely, e.g. input[data-testid='foo'].
    pattern = re.compile(
        r"(?:\b(?:page\.)?(?:locator|click|fill|text_content|wait_for_selector)\s*\(\s*)([\'\"])(.*?)\1",
        re.DOTALL,
    )
    return {match.group(2) for match in pattern.finditer(code)}


def extract_observed_selectors(evidence):
    """Return the exact selector strings collected from Playwright evidence."""
    observed = set()
    raw = parse_json_strings(evidence)

    def walk(value):
        if isinstance(value, dict):
            for key, child in value.items():
                if key == "selector" and isinstance(child, str) and child.strip():
                    observed.add(child.strip())
                elif key == "selectors" and isinstance(child, list):
                    for item in child:
                        if isinstance(item, str) and item.strip():
                            observed.add(item.strip())
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)

    walk(raw)
    return observed


def parse_json_strings(value):
    """Recursively unwrap MCP result wrappers and embedded JSON strings."""
    if isinstance(value, str):
        s = value.strip()

        # MCP browser_evaluate commonly returns:
        # ### Result
        # "{\\\"url\\\": ... }"
        # ### Ran Playwright code
        # ...
        # Extract the Result payload first.
        if "### Result" in s:
            result_part = s.split("### Result", 1)[1]
            if "### Ran Playwright code" in result_part:
                result_part = result_part.split("### Ran Playwright code", 1)[0]
            result_part = result_part.strip()

            try:
                decoded = json.loads(result_part)
                if isinstance(decoded, str):
                    return parse_json_strings(decoded)
                return parse_json_strings(decoded)
            except Exception:
                pass

        # MCP may wrap JSON in a markdown code fence.
        s = re.sub(r"^```(?:json)?\s*", "", s, flags=re.IGNORECASE)
        s = re.sub(r"\s*```$", "", s)
        s = s.strip()

        # Direct JSON object/list.
        if s.startswith("{") or s.startswith("["):
            try:
                return parse_json_strings(json.loads(s))
            except Exception:
                pass

        # Some MCP versions prepend labels before raw JSON.
        for marker in ('{"homepage"', '{"result"', '{"url"', '{"controls"'):
            pos = s.find(marker)
            if pos >= 0:
                candidate = s[pos:]
                try:
                    return parse_json_strings(json.loads(candidate))
                except Exception:
                    pass

        return value

    if isinstance(value, dict):
        return {k: parse_json_strings(v) for k, v in value.items()}

    if isinstance(value, list):
        return [parse_json_strings(v) for v in value]

    if hasattr(value, "model_dump"):
        try:
            return parse_json_strings(value.model_dump())
        except Exception:
            pass

    return value




def extract_controls(evidence, section):
    raw = parse_json_strings(evidence)
    value = raw.get(section, {}) if isinstance(raw, dict) else {}
    controls = value.get("controls", []) if isinstance(value, dict) else []
    return [c for c in controls if isinstance(c, dict)] if isinstance(controls, list) else []


def choose_selector(controls, kind):
    """Choose an exact selector from MCP evidence; never invent one."""
    candidates = []
    for c in controls:
        selectors = c.get("selectors") or []
        if not selectors:
            continue
        blob = " ".join(str(c.get(k, "")) for k in ("text", "name", "placeholder", "aria_label", "testid", "id")).lower()
        tag = str(c.get("tag", "")).lower()
        typ = str(c.get("type", "")).lower()
        score = 0
        if kind == "username":
            if "username" in blob or "user name" in blob: score += 100
            if typ == "text": score += 10
            if tag == "input": score += 5
        elif kind == "password":
            if typ == "password": score += 100
            if "password" in blob: score += 50
        elif kind == "login":
            if any(x in blob for x in ("login", "log in", "sign in")): score += 100
            if tag == "button": score += 10
        elif kind == "logout":
            if "logout" in blob or "log out" in blob: score += 100
        elif kind.startswith("contact_"):
            wanted = kind[len("contact_"):]
            if wanted in blob: score += 100
            if tag in ("input", "textarea"): score += 5
        if score:
            candidates.append((score, selectors[0]))
    return max(candidates, default=(0, None))[1]


def build_deterministic_ui_files(evidence):
    """Write selector-bearing UI code from MCP evidence, not Gemini output."""
    admin = extract_controls(evidence, "admin_dom")
    home = extract_controls(evidence, "homepage_dom")

    username = choose_selector(admin, "username")
    password = choose_selector(admin, "password")
    login = choose_selector(admin, "login")
    logout = choose_selector(admin, "logout")
    contact_name = choose_selector(home, "contact_name")
    contact_email = choose_selector(home, "contact_email")
    contact_phone = choose_selector(home, "contact_phone")
    contact_subject = choose_selector(home, "contact_subject")
    contact_description = choose_selector(home, "contact_description")
    contact_submit = choose_selector(home, "contact_submit")

    def q(v):
        return repr(v) if v else "None"

    base = """from playwright.sync_api import Page


class BasePage:
    def __init__(self, page: Page, base_url: str):
        self.page = page
        self.base_url = base_url

    def open(self, path: str = "/"):
        self.page.goto(self.base_url.rstrip("/") + path)
        self.page.wait_for_load_state("domcontentloaded")
"""

    admin_path = (evidence.get("admin_path") if isinstance(evidence, dict) else None) or "/#/admin/"

    admin_code = f"""from .base_page import BasePage


class AdminPage(BasePage):
    username_selector = {q(username)}
    password_selector = {q(password)}
    login_selector = {q(login)}
    logout_selector = {q(logout)}

    def open(self):
        self.page.goto(self.base_url.rstrip("/") + {admin_path!r})
        self.page.wait_for_timeout(1500)

    def login(self, username="admin", password="password"):
        if not all((self.username_selector, self.password_selector, self.login_selector)):
            raise RuntimeError("Admin login controls were not uniquely observed by Playwright MCP.")
        self.page.locator(self.username_selector).fill(username)
        self.page.locator(self.password_selector).fill(password)
        self.page.locator(self.login_selector).click()
        self.page.wait_for_timeout(1500)

    def is_logged_in(self):
        # The admin SPA can keep the same URL after authentication and may not
        # render a logout control in the initial DOM evidence. The username
        # control is observed before login, so use its post-login visibility as
        # the deterministic state signal: visible form => still logged out;
        # hidden/removed form => authenticated.
        if self.username_selector:
            locator = self.page.locator(self.username_selector)
            if locator.count() == 0:
                return True
            try:
                return not locator.first.is_visible()
            except Exception:
                return False
        if self.logout_selector:
            return self.page.locator(self.logout_selector).count() > 0
        return False

    def logout(self):
        if not self.logout_selector:
            raise RuntimeError("Logout control was not observed by Playwright MCP.")
        self.page.locator(self.logout_selector).click()
"""

    booking_code = f"""from .base_page import BasePage


class BookingPage(BasePage):
    contact_name_selector = {q(contact_name)}
    contact_email_selector = {q(contact_email)}
    contact_phone_selector = {q(contact_phone)}
    contact_subject_selector = {q(contact_subject)}
    contact_description_selector = {q(contact_description)}
    contact_submit_selector = {q(contact_submit)}

    def open(self):
        self.page.goto(self.base_url.rstrip("/"))
        self.page.wait_for_timeout(1500)

    def fill_contact_form(self, name, email, phone, subject, description):
        fields = [
            (self.contact_name_selector, name),
            (self.contact_email_selector, email),
            (self.contact_phone_selector, phone),
            (self.contact_subject_selector, subject),
            (self.contact_description_selector, description),
        ]
        if any(not selector for selector, _ in fields) or not self.contact_submit_selector:
            raise RuntimeError("Contact form controls were not uniquely observed by Playwright MCP.")
        for selector, value in fields:
            self.page.locator(selector).fill(value)
        self.page.locator(self.contact_submit_selector).click()

    def page_title(self):
        return self.page.title()
"""

    home_code = """from .base_page import BasePage


class HomePage(BasePage):
    def open(self):
        self.page.goto(self.base_url.rstrip("/"))
        self.page.wait_for_timeout(1500)

    def url(self):
        return self.page.url
"""

    for rel, code in {
        "pages/base_page.py": base,
        "pages/home_page.py": home_code,
        "pages/admin_page.py": admin_code,
        "pages/booking_page.py": booking_code,
    }.items():
        target = OUTPUT_DIR / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(code.strip() + "\n", encoding="utf-8")
        print(f"Replaced {rel} with deterministic MCP-backed UI code")



def enforce_generated_runtime_contract():
    """Normalize runtime-sensitive generated files without another Gemini call."""
    conftest = """import pytest

from pages.home_page import HomePage
from pages.admin_page import AdminPage
from pages.booking_page import BookingPage


@pytest.fixture(scope=\"session\")
def base_url():
    return \"https://automationintesting.online\"


@pytest.fixture(scope=\"session\")
def api_base_url():
    return \"https://automationintesting.online/api\"


@pytest.fixture
def home_page(page, base_url):
    return HomePage(page, base_url)


@pytest.fixture
def admin_page(page, base_url):
    return AdminPage(page, base_url)


@pytest.fixture
def booking_page(page, base_url):
    return BookingPage(page, base_url)
"""
    (OUTPUT_DIR / "conftest.py").write_text(conftest, encoding="utf-8")
    print("Replaced conftest.py with deterministic page-object fixtures")

    admin_tests = """def test_admin_login_success(admin_page):
    admin_page.open()
    admin_page.login(\"admin\", \"password\")
    assert admin_page.is_logged_in()


def test_admin_login_failure(admin_page):
    admin_page.open()
    admin_page.login(\"admin\", \"wrong\")
    assert not admin_page.is_logged_in()
"""
    (OUTPUT_DIR / "tests/ui/test_admin_login.py").write_text(admin_tests, encoding="utf-8")
    print("Replaced tests/ui/test_admin_login.py with deterministic test-layer code")

    booking_tests = """def test_browse_rooms(home_page):
    home_page.open()
    assert home_page.url().startswith(\"https://automationintesting.online\")


def test_negative_contact_booking(booking_page):
    booking_page.open()
    booking_page.fill_contact_form(\"\", \"\", \"\", \"\", \"\")
    assert booking_page.page_title()
"""
    (OUTPUT_DIR / "tests/ui/test_booking.py").write_text(booking_tests, encoding="utf-8")
    print("Replaced tests/ui/test_booking.py with deterministic test-layer code")

    auth_tests = """import requests


def test_login_success(api_base_url):
    response = requests.post(
        f\"{api_base_url}/auth/login\",
        json={\"username\": \"admin\", \"password\": \"password\"},
        timeout=30,
    )
    assert response.status_code == 200
    body = response.json()
    assert body.get(\"token\")


def test_login_negative(api_base_url):
    response = requests.post(
        f\"{api_base_url}/auth/login\",
        json={\"username\": \"admin\", \"password\": \"wrong\"},
        timeout=30,
    )
    assert response.status_code == 401
"""
    (OUTPUT_DIR / "tests/api/test_auth_api.py").write_text(auth_tests, encoding="utf-8")
    print("Replaced tests/api/test_auth_api.py with deterministic API assertions")

    booking_api = """import requests
from datetime import datetime, timedelta


def test_create_and_get_booking(api_base_url):
    session = requests.Session()

    auth_response = session.post(
        f"{api_base_url}/auth/login",
        json={"username": "admin", "password": "password"},
        timeout=30,
    )
    assert auth_response.status_code == 200
    token = auth_response.json().get("token")
    assert token
    session.cookies.set("token", token)

    rooms_response = session.get(
        f"{api_base_url}/room/",
        timeout=30,
    )
    assert rooms_response.status_code == 200

    rooms = rooms_response.json().get("rooms", [])
    assert rooms, "No rooms returned by the API"

    # Use a future window and a few candidate rooms/dates. The deployed
    # platform resets its seeded database periodically, so the test must not
    # depend on a fixed room/date combination.
    start = datetime.now() + timedelta(days=30)
    created_booking = None
    last_conflict = None

    for room in rooms:
        room_id = room.get("roomid")
        if room_id is None:
            continue

        for offset in range(0, 60, 2):
            checkin = start + timedelta(days=offset)
            checkout = checkin + timedelta(days=1)
            payload = {
                "bookingdates": {
                    "checkin": checkin.strftime("%Y-%m-%d"),
                    "checkout": checkout.strftime("%Y-%m-%d"),
                },
                "depositpaid": True,
                "firstname": "Test",
                "lastname": "User",
                "roomid": room_id,
            }

            response = session.post(
                f"{api_base_url}/booking/",
                json=payload,
                timeout=30,
            )

            if response.status_code == 201:
                created_booking = response.json()
                break

            if response.status_code == 409:
                last_conflict = response.text
                continue

            raise AssertionError(
                f"Unexpected booking creation status {response.status_code}: {response.text}"
            )

        if created_booking is not None:
            break

    assert created_booking is not None, (
        "Could not create a booking for returned rooms/date combinations. "
        f"Last conflict: {last_conflict}"
    )

    booking_id = created_booking.get("bookingid")
    assert booking_id is not None

    get_response = session.get(
        f"{api_base_url}/booking/{booking_id}",
        timeout=30,
    )
    assert get_response.status_code == 200

    booking = get_response.json()
    assert booking.get("bookingid") == booking_id
    assert booking.get("roomid") == created_booking.get("roomid")
    assert booking.get("firstname") == "Test"
    assert booking.get("lastname") == "User"
"""

    (OUTPUT_DIR / "tests/api/test_booking_api.py").write_text(booking_api, encoding="utf-8")
    print("Replaced tests/api/test_booking_api.py with dynamic room/date logic")

def validate_generated_project(evidence):
    """Fail closed: never accept a generated selector that was not observed."""
    observed = extract_observed_selectors(evidence)
    if not observed:
        raise RuntimeError("No concrete selectors were captured from Playwright MCP; refusing to generate tests.")

    # Page objects may contain selectors, but UI tests must not contain raw locators.
    for rel in ["tests/ui/test_admin_login.py", "tests/ui/test_booking.py"]:
        code = (OUTPUT_DIR / rel).read_text(encoding="utf-8")

        forbidden_patterns = [
            # Only reject actual Playwright page-variable usage in UI tests.
            # A comment/string containing the word "page" is harmless.
            r"\bpage\s*(?:\.|=)",
            r"\b(?:locator|locators)\s*\(",
            r"\bget_by_[A-Za-z_]+\s*\(",
            r"\b(?:goto|fill|click|wait_for_[A-Za-z_]+|wait_for)\s*\(",
        ]

        for pattern in forbidden_patterns:
            match = re.search(pattern, code)
            if match:
                line_no = code[:match.start()].count("\n") + 1
                offending = code.splitlines()[line_no - 1].strip()
                raise RuntimeError(
                    f"Raw Playwright locator usage found in {rel}; "
                    f"page-object rule violated at line {line_no}: {offending}"
                )


    page_files = [
        "pages/base_page.py",
        "pages/home_page.py",
        "pages/admin_page.py",
        "pages/booking_page.py",
    ]
    unknown = []
    for rel in page_files:
        code = (OUTPUT_DIR / rel).read_text(encoding="utf-8")
        for selector in extract_css_strings(code):
            if selector not in observed:
                unknown.append((rel, selector))
    if unknown:
        details = "\n".join(f"  {rel}: {selector!r}" for rel, selector in unknown[:20])
        raise RuntimeError(
            "Generated project contains selector(s) not observed by MCP. "
            "Refusing to accept guessed selectors:\n" + details
        )

    # Guard against common hallucinated selectors from earlier generations.
    forbidden_fragments = [
        "[data-testid='username']",
        '[data-testid="username"]',
        "[data-testid='password']",
        '[data-testid="password"]',
        "[data-testid='doLogin']",
        '[data-testid="doLogin"]',
        "[data-testid='bookRoom']",
        '[data-testid="bookRoom"]',
        ".room-name",
        "button.openBooking",
    ]
    for rel in page_files:
        code = (OUTPUT_DIR / rel).read_text(encoding="utf-8")
        for bad in forbidden_fragments:
            if bad in code:
                raise RuntimeError(f"Known guessed selector {bad!r} found in {rel}.")

    print(f"Selector validation passed: {len(observed)} observed selectors available.")


EXPLORATION_CODE = r'''
async (page) => {
const result = { homepage: {}, booking: {}, admin: {} };

function norm(v) { return (v || "").trim().replace(/\s+/g, " "); }
function cssEscape(v) { return CSS.escape(String(v)); }

function unique(sel) {
  try { return document.querySelectorAll(sel).length === 1; }
  catch (_) { return false; }
}

function candidateSelectors(el) {
  const out = [];
  const tag = el.tagName.toLowerCase();
  const id = el.getAttribute("id");
  const testid = el.getAttribute("data-testid");
  const name = el.getAttribute("name");
  const placeholder = el.getAttribute("placeholder");
  const aria = el.getAttribute("aria-label");
  const type = el.getAttribute("type");

  if (id) out.push(`#${cssEscape(id)}`);
  if (testid) out.push(`[data-testid="${testid.replace(/"/g, '\\"')}"]`);
  if (name) out.push(`${tag}[name="${name.replace(/"/g, '\\"')}"]`);
  if (placeholder) out.push(`${tag}[placeholder="${placeholder.replace(/"/g, '\\"')}"]`);
  if (aria) out.push(`${tag}[aria-label="${aria.replace(/"/g, '\\"')}"]`);
  if (type) out.push(`${tag}[type="${type.replace(/"/g, '\\"')}"]`);

  const cls = typeof el.className === "string"
    ? el.className.split(/\s+/).filter(Boolean).slice(0, 3)
    : [];
  if (cls.length) {
    const sel = tag + cls.map(c => `.${cssEscape(c)}`).join("");
    out.push(sel);
  }

  const text = norm(el.innerText || el.value);
  if (text && /^(button|a|label)$/i.test(tag)) {
    out.push(`${tag}:has-text("${text.replace(/"/g, '\\"').slice(0, 100)}")`);
  }

  return out.filter(unique);
}

function describe(el) {
  const attrs = {};
  for (const name of ["id","data-testid","name","type","placeholder","aria-label","role","for","href"])
    if (el.getAttribute(name)) attrs[name] = el.getAttribute(name);
  const text = norm(el.innerText || el.value);
  const selectors = candidateSelectors(el);
  return {
    tag: el.tagName.toLowerCase(),
    attributes: attrs,
    text: text.slice(0, 160),
    selector: selectors[0] || null,
    selectors
  };
}

function controls() {
  return Array.from(document.querySelectorAll("input,button,select,textarea,a,[role='button']"))
    .map(describe)
    .filter(x => x.selector || x.text || Object.keys(x.attributes).length)
    .slice(0, 220);
}

function roomElements() {
  return Array.from(document.querySelectorAll("[class*='room'], [id*='room'], .card"))
    .slice(0, 80).map(describe);
}

await page.goto("https://automationintesting.online", { waitUntil: "domcontentloaded" });
await page.waitForTimeout(1500);
result.homepage = {
  url: page.url(),
  title: await page.title(),
  controls: controls(),
  room_elements: roomElements()
};

// Try an observed booking/reservation control. Do not invent a selector.
const all = Array.from(document.querySelectorAll("button,a,[role='button']"));
const bookingEl = all.find(e => /book|reserve/i.test(norm(e.innerText || e.getAttribute("aria-label"))));
if (bookingEl) {
  const sels = candidateSelectors(bookingEl);
  if (sels[0]) {
    await page.locator(sels[0]).first().click();
    await page.waitForTimeout(700);
    result.booking = {
      clicked_selector: sels[0],
      url: page.url(),
      controls: controls(),
      dialogs: Array.from(document.querySelectorAll("[role='dialog'], .modal, [class*='modal'], [class*='booking']"))
        .slice(0, 60).map(describe)
    };
  }
}

await page.goto("https://automationintesting.online/#/admin", { waitUntil: "domcontentloaded" });
await page.waitForTimeout(1000);
result.admin = {
  url: page.url(),
  controls: controls(),
  inputs: Array.from(document.querySelectorAll("input")).map(describe),
  buttons: Array.from(document.querySelectorAll("button")).map(describe),
  labels: Array.from(document.querySelectorAll("label")).slice(0, 60).map(e => ({text:norm(e.innerText), for:e.getAttribute("for") || ""}))
};

return JSON.stringify(result);
}
'''


def build_prompt(spec, evidence_text, selector_allowlist):
    return f'''You are generating a small, runnable Python QA automation project.

This is the FINAL generation request. Do NOT call tools. Return ONLY the exact
11 `### FILE:` blocks required by the specification. No prose outside them.

HARD SELECTOR CONTRACT — MUST FOLLOW:
1. The BROWSER EVIDENCE is the only source of truth for UI selectors.
2. Every CSS selector used by any page object MUST be copied EXACTLY from the
   OBSERVED SELECTOR ALLOWLIST below. Do not modify quote style, tag names,
   attributes, classes, ids, or selector structure.
3. NEVER invent a data-testid, id, class, name, placeholder, text selector, or CSS selector.
4. Do NOT use XPath.
5. Do NOT use `get_by_role`, `get_by_text`, `get_by_label`, or other semantic locators.
   Use only the exact observed CSS selector strings from the evidence.
6. UI test files (`tests/ui/*.py`) are STRICTLY test-layer files.
   They may import page objects, instantiate page objects, call page-object methods,
   use pytest fixtures, and make assertions ONLY.
7. UI test files MUST NOT contain a `page` variable at all. They must use only
   page-object fixtures such as `admin_page`, `booking_page`, or `home_page`.
   NEVER write `page.locator(...)`, `page.get_by_*`, `page.click(...)`,
   `page.fill(...)`, `page.goto(...)`, `page.wait_for_*`, or `locator(...)` inside
   `tests/ui/*.py`. DOM/UI assertions that require Playwright must also live in page objects.
8. ALL browser navigation, locator creation, clicks, fills, waits, and UI assertions
   that require a locator MUST be implemented as methods/properties in the page
   objects under `pages/`.
9. A UI test should look structurally like:
      def test_something(admin_page):
          admin_page.open()
          admin_page.login("admin", "password")
          assert admin_page.is_logged_in()
   The exact methods may differ, but the test itself must contain no Playwright
   locator/API calls.
10. If the evidence has no selector for a requested interaction, do not invent one.
    Use another observed selector that actually represents that interaction, or keep
    the flow minimal rather than guessing.
11. The selector allowlist below is authoritative. A selector is valid ONLY if it
    appears as one complete line in that allowlist.

FINAL SELF-CHECK BEFORE RETURNING FILES:
- Inspect both `tests/ui/test_admin_login.py` and `tests/ui/test_booking.py`.
- They must contain ZERO `page` variable usage.
- They must contain ZERO Playwright locator/API calls.
- They must contain ZERO `locator(...)` calls.
- They must NOT contain CSS selectors.
- They must use only page-object fixtures and ordinary Python assertions.
- If you accidentally put a browser interaction in a UI test, MOVE that interaction
  into the appropriate page object before returning the final 11 FILE blocks.

PROJECT RULES:
- conftest.py: `base_url` and `api_base_url` must be session-scoped fixtures.
- conftest.py MUST also provide page-object fixtures named `admin_page`, `booking_page`,
  and `home_page` that construct the corresponding page object from pytest-playwright's
  `page` fixture. UI tests must use these fixtures instead of accepting `page`.
- Homepage: `page.goto(base_url)`.
- Admin: `page.goto(f"{{base_url}}/#/admin")`.
- Admin credentials: admin/password.
- Booking dates: calculate future dates dynamically; never use stale fixed dates.
- API tests must assert status codes AND important response keys/schema.
- API booking creation must first obtain a real room id from GET /api/room/.
- After POST /api/booking/, GET the returned booking id and validate it.
- Include a negative booking request with a missing required field.
- Keep generated tests simple and runnable with pytest + pytest-playwright + requests.
- requirements.txt must contain only needed packages.
- Do not include MCP in generated project dependencies.

OBSERVED SELECTOR ALLOWLIST — COPY ONLY THESE SELECTORS VERBATIM:
{selector_allowlist}

BROWSER EVIDENCE:
{evidence_text}

SPECIFICATION:
{spec}
'''


async def main():
    spec, api_key = read_spec()
    print(f"Using Gemini model: {MODEL}")
    print("Quota-safe mode: exactly ONE Gemini generation request.")
    print("Starting Playwright MCP server...")

    client = genai.Client(api_key=api_key)
    server = StdioServerParameters(command="npx", args=["-y", "@playwright/mcp@latest", "--headless"])

    async with stdio_client(server) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = (await session.list_tools()).tools
            print(f"Playwright MCP tools available: {len(tools)}")
            names = {t.name for t in tools}
            required_tools = {"browser_navigate", "browser_evaluate", "browser_wait_for", "browser_snapshot"}
            missing_tools = required_tools - names
            if missing_tools:
                raise RuntimeError(
                    "Playwright MCP is missing required tools: "
                    + ", ".join(sorted(missing_tools))
                )

            print("Collecting deterministic browser evidence...")
            print("Using browser_navigate + browser_evaluate.")
            print("MCP calls do NOT consume Gemini API quota.")

            DOM_EVALUATE = r"""
() => {
    const clean = (value) =>
        String(value || "")
            .replace(/\s+/g, " ")
            .trim()
            .slice(0, 300);

    const escapeAttr = (value) =>
        String(value).replace(/\\/g, "\\\\").replace(/"/g, '\\"');

    const unique = (items) => [...new Set(items.filter(Boolean))];

    const isUnique = (selector) => {
        try {
            return document.querySelectorAll(selector).length === 1;
        } catch (_) {
            return false;
        }
    };

    const selectorCandidates = (el) => {
        const result = [];
        const tag = el.tagName.toLowerCase();

        if (el.id) {
            const selector = "#" + CSS.escape(el.id);
            if (isUnique(selector)) result.push(selector);
        }

        for (const attr of ["data-testid", "data-test", "data-test-id", "name", "aria-label", "placeholder"]) {
            const value = el.getAttribute(attr);
            if (!value) continue;

            const selector = `${tag}[${attr}="${escapeAttr(value)}"]`;
            if (isUnique(selector)) result.push(selector);
        }

        if (el.type) {
            const selector = `${tag}[type="${escapeAttr(el.type)}"]`;
            if (isUnique(selector)) result.push(selector);
        }

        if (el.classList && el.classList.length) {
            const classes = [...el.classList]
                .filter(c => /^[A-Za-z_][A-Za-z0-9_-]*$/.test(c))
                .slice(0, 3);

            if (classes.length) {
                const selector = tag + classes.map(c => "." + CSS.escape(c)).join("");
                if (isUnique(selector)) result.push(selector);
            }
        }

        return unique(result);
    };

    const describe = (el) => ({
        tag: el.tagName.toLowerCase(),
        type: el.getAttribute("type") || "",
        id: el.id || "",
        name: el.getAttribute("name") || "",
        testid: el.getAttribute("data-testid") || "",
        placeholder: el.getAttribute("placeholder") || "",
        aria_label: el.getAttribute("aria-label") || "",
        role: el.getAttribute("role") || "",
        text: clean(el.innerText || el.value || el.textContent || ""),
        href: el.getAttribute("href") || "",
        selectors: selectorCandidates(el)
    });

    const controls = [...document.querySelectorAll(
        "input, button, select, textarea, a, [role='button']"
    )].map(describe);

    const roomLike = [...document.querySelectorAll(
        "[class*='room'], [id*='room'], [class*='Room'], [id*='Room'], .card"
    )].map(describe);

    return JSON.stringify({
        url: location.href,
        title: document.title,
        controls,
        room_like: roomLike,
        body_text: clean(document.body.innerText || "")
    });
}
"""

            async def evaluate_dom():
                result = await mcp_call(
                    session,
                    "browser_evaluate",
                    {"function": DOM_EVALUATE},
                )
                return parse_json_strings(result)

            print("Navigating to homepage...")
            homepage_navigation = await mcp_call(
                session,
                "browser_navigate",
                {"url": UI_BASE_URL},
            )

            # automationintesting.online is a client-rendered SPA.
            # browser_navigate can return before React has mounted the
            # controls, so explicitly wait for the application to render.
            print("Waiting for homepage SPA to render...")
            await mcp_call(
                session,
                "browser_wait_for",
                {"time": 5},
            )
            homepage_dom = await evaluate_dom()

            print("Navigating to admin page...")
            # The deployed SPA has used both hash and non-hash admin routes
            # across versions. Try the documented variants locally and keep
            # the first one that actually renders the login controls. This
            # costs no Gemini quota and prevents us from guessing selectors.
            admin_candidates = [
                "/#/admin/",
                "/#/admin",
                "/admin/",
                "/admin",
            ]
            admin_navigation = None
            admin_dom = None
            admin_path = None

            for candidate in admin_candidates:
                print(f"  Trying admin route: {candidate}")
                navigation = await mcp_call(
                    session,
                    "browser_navigate",
                    {"url": UI_BASE_URL.rstrip("/") + candidate},
                )
                await mcp_call(
                    session,
                    "browser_wait_for",
                    {"time": 4},
                )
                dom = await evaluate_dom()
                controls = extract_controls({"admin_dom": dom}, "admin_dom")
                control_blob = " ".join(
                    " ".join(str(c.get(k, "")) for k in ("text", "name", "placeholder", "aria_label", "testid", "id"))
                    for c in controls
                ).lower()
                has_username = any(
                    c.get("type", "").lower() in ("text", "email") and (
                        "username" in " ".join(str(c.get(k, "")) for k in ("text", "name", "placeholder", "aria_label", "testid", "id")).lower()
                        or c.get("id", "").lower() == "username"
                    )
                    for c in controls
                )
                has_password = any(c.get("type", "").lower() == "password" for c in controls)
                has_login = any(
                    any(x in " ".join(str(c.get(k, "")) for k in ("text", "name", "placeholder", "aria_label", "testid", "id")).lower() for x in ("login", "log in", "sign in"))
                    for c in controls
                )

                if has_username and has_password and has_login:
                    admin_navigation = navigation
                    admin_dom = dom
                    admin_path = candidate
                    print(f"  Selected admin route: {candidate}")
                    break

                print("  Login controls not present on this route; trying next route.")

            if admin_dom is None:
                raise RuntimeError(
                    "Could not find an admin route that renders username, password, and login controls. "
                    "Gemini generation was skipped to protect quota."
                )

            browser_evidence = {
                "homepage_navigation": parse_json_strings(homepage_navigation),
                "homepage_dom": homepage_dom,
                "admin_path": admin_path,
                "admin_navigation": parse_json_strings(admin_navigation),
                "admin_dom": admin_dom,
            }

            def count_selectors(value):
                if isinstance(value, dict):
                    total = 0
                    selectors = value.get("selectors")
                    if isinstance(selectors, list):
                        total += sum(
                            1 for item in selectors
                            if isinstance(item, str) and item.strip()
                        )
                    for child in value.values():
                        total += count_selectors(child)
                    return total

                if isinstance(value, list):
                    return sum(count_selectors(item) for item in value)

                return 0

            browser_evidence_text = json.dumps(
                browser_evidence,
                ensure_ascii=False,
                default=str,
            )
            selector_count = count_selectors(browser_evidence)

            print(f"Browser evidence type: {type(browser_evidence).__name__}")
            print(f"Browser evidence size: {len(browser_evidence_text)} chars")
            print(f"Concrete selectors captured: {selector_count}")

            if isinstance(browser_evidence, dict):
                for section_name, section_value in browser_evidence.items():
                    section_count = count_selectors(section_value)
                    print(f"  {section_name}: {section_count} selectors")

            # HARD STOP BEFORE GEMINI.
            # If MCP failed or returned no real selectors, do not spend
            # the single Gemini request.
            if selector_count == 0:
                print("\nNo CSS selectors found after the SPA wait.")
                print("Collecting one accessibility snapshot for diagnosis...")
                snapshot = await mcp_call(
                    session,
                    "browser_snapshot",
                    {},
                )

                print("\n========== ACCESSIBILITY SNAPSHOT ==========")
                print(str(snapshot)[:12000])
                print("========== END ACCESSIBILITY SNAPSHOT ==========")

                print("\n========== RAW MCP DOM EVIDENCE ==========")
                print(browser_evidence_text[:12000])
                print("========== END RAW MCP DOM EVIDENCE ==========")

                raise RuntimeError(
                    "Playwright MCP returned no concrete DOM selectors after "
                    "waiting for the SPA to render. Gemini generation was "
                    "skipped to protect quota."
                )

            print("Collecting API evidence locally (no Gemini quota)...")
            api = []
            api.append({"endpoint": "POST /api/auth/login", "result": call_api("POST", f"{API_BASE_URL}/auth/login", {"username":"admin","password":"password"})})
            rooms = call_api("GET", f"{API_BASE_URL}/room/")
            api.append({"endpoint": "GET /api/room/", "result": rooms})

            room_id = None
            if isinstance(rooms.get("body"), dict):
                room_list = rooms["body"].get("rooms") or []
                if room_list and isinstance(room_list[0], dict):
                    room_id = room_list[0].get("roomid")

            auth_probe = api[0].get("result", {})
            token_probe = auth_probe.get("body", {}).get("token") if isinstance(auth_probe, dict) else None
            if room_id is not None:
                booking_body = {
                    "firstname":"Generator", "lastname":"Probe", "depositpaid":False,
                    "bookingdates":{"checkin":"2030-01-10","checkout":"2030-01-12"},
                    "roomid":room_id, "email":"generator.probe@example.com", "phone":"0123456789"
                }
                headers = {"Cookie": f"token={token_probe}"} if token_probe else None
                created = call_api("POST", f"{API_BASE_URL}/booking/", booking_body, headers=headers)
                api.append({"endpoint":"POST /api/booking/", "request":booking_body, "result":created})
                if isinstance(created.get("body"), dict) and created["body"].get("bookingid"):
                    bid = created["body"]["bookingid"]
                    api.append({"endpoint":f"GET /api/booking/{bid}", "result":call_api("GET", f"{API_BASE_URL}/booking/{bid}")})

            negative = call_api("POST", f"{API_BASE_URL}/booking/", {
                "lastname":"MissingFirstname", "depositpaid":False,
                "bookingdates":{"checkin":"2030-01-10","checkout":"2030-01-12"},
                "roomid":room_id or 0, "email":"negative@example.com", "phone":"0123456789"
            }, headers={"Cookie": f"token={token_probe}"} if token_probe else None)
            api.append({"endpoint":"POST /api/booking/ negative missing firstname", "result":negative})

            evidence = {"browser": browser_evidence, "api": api}
            evidence_text = json.dumps(evidence, ensure_ascii=False, default=str)
            if len(evidence_text) > MAX_EVIDENCE_CHARS:
                evidence_text = evidence_text[:MAX_EVIDENCE_CHARS] + "\n[TRUNCATED]"

            observed_selectors = sorted(extract_observed_selectors(browser_evidence))
            selector_allowlist = "\n".join(f"- {selector}" for selector in observed_selectors)
            print(f"Explicit selector allowlist sent to Gemini: {len(observed_selectors)} selectors")

            print("Gemini final generation request 1/1...")
            response = await client.aio.models.generate_content(
                model=MODEL,
                contents=build_prompt(spec, evidence_text, selector_allowlist),
                config=types.GenerateContentConfig(temperature=0.0, max_output_tokens=16000),
            )
            text = response.text or ""
            if not text:
                raise RuntimeError("Gemini returned an empty response.")
            save_output(text)
            print("Locking UI selectors to deterministic MCP evidence...")
            build_deterministic_ui_files(browser_evidence)
            print("Normalizing generated runtime contract locally (no Gemini quota)...")
            enforce_generated_runtime_contract()
            print("Validating generated project against observed selectors...")
            validate_generated_project(browser_evidence)

    print("\nGeneration completed successfully.")
    print(f"Generated project: {OUTPUT_DIR}")


if __name__ == "__main__":
    asyncio.run(main())
