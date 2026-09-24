# UI Testing Specification
# Restful Booker Platform — automationintesting.online

## Application Overview

The Restful Booker Platform is a hotel/B&B booking demo application.
It allows visitors to browse rooms, make reservations, and contact the property.
An admin interface allows staff to manage rooms, bookings, and messages.

**UI Base URL:** Defined in .env as `UI_BASE_URL`

---

## UI Workflows to Automate

---

### WORKFLOW 1 — Home Page Validation

**Purpose:** Verify that the application loads successfully and primary
elements are visible.

**Steps:**
1. Navigate to the base URL
2. Confirm the page loads without error
3. Verify the main navigation is visible
4. Verify key home-page content is displayed (hero section, rooms section, etc.)
5. Verify the page title is meaningful

**Expected Behavior:**
- Page loads with HTTP 200
- Navigation items are discoverable from the accessibility tree
- Room information section is present
- Footer is present

---

### WORKFLOW 2 — Primary Navigation

**Purpose:** Validate that primary navigation links are functional.

**Discovery Rule:**
Navigation items must be discovered dynamically from the accessibility snapshot.
Do NOT hardcode navigation link names or href values.

**Steps:**
1. Open the home page
2. Discover all navigation links from the accessibility tree
3. For each discovered link: verify it is clickable and resolves to a valid page
4. Record navigation items found

**Expected Behavior:**
- All discovered navigation links are functional
- Navigation does not result in 404 or error pages

---

### WORKFLOW 3 — Rooms Workflow (Dynamic Discovery)

**Purpose:** Dynamically discover available rooms and navigate to
the booking/reservation page.

**Discovery Rules:**
- Room cards MUST be discovered from the DOM/accessibility tree
- Do NOT hardcode room names (Single, Double, Suite, etc.)
- Do NOT hardcode room IDs
- The section heading "Our Rooms" must NOT be treated as a room
- Room discovery should identify cards containing both a room name/type
  AND a booking action (button/link)

**Steps:**
1. Navigate to the home page
2. Identify the rooms/accommodations section
3. Discover all room cards dynamically
4. Select the first available room card that has a booking action
5. Click the booking action (e.g., "Book Now" or similar CTA)
6. Verify navigation to the reservation/booking page

**Evidence to Collect:**
- List of discovered rooms (names, types)
- Selected room details
- The booking action element reference
- The reservation page URL
- Reservation page content

---

### WORKFLOW 4 — Reservation Page Workflow

**Purpose:** Validate the reservation/booking flow after selecting a room.

**Steps:**
1. Navigate to a room's reservation page (URL from Workflow 3)
2. Identify the booking/calendar section
3. Identify date selection controls
4. Identify the "Reserve Now" or equivalent primary booking action
5. Collect all visible booking-related fields and controls
6. Record price/rate information if displayed

**Discovery Rules:**
- Distinguish booking controls from global navigation and footer
- Use semantic/structural evidence (heading hierarchy, form grouping)
- Do NOT filter controls by hardcoded button name lists

**Expected Behavior:**
- Reservation page loads successfully
- A date/calendar picker is present
- A primary booking action exists
- Booking form fields are identifiable

---

### WORKFLOW 5 — Admin Login

**Purpose:** Validate admin authentication workflow.

**Credentials:** Loaded from .env (ADMIN_USERNAME, ADMIN_PASSWORD)
**Admin Path:** Loaded from .env (ADMIN_PATH)

**Steps:**
1. Navigate to admin URL (UI_BASE_URL + ADMIN_PATH)
2. Identify the username input field
3. Identify the password input field
4. Identify the login/submit button
5. Enter credentials from .env
6. Submit the login form
7. Verify successful authentication (dashboard visible, login form gone)

**Expected Behavior:**
- Admin login page is accessible
- Username and password fields are present
- Login action is present
- After valid credentials: dashboard is visible
- After invalid credentials: error message is shown (negative scenario)

---

### WORKFLOW 6 — Booking Workflow

**Purpose:** Complete an end-to-end room booking flow.

**Rules:**
- Use dynamically generated guest data (name, email, phone)
- Use runtime-calculated dates (relative to today, never hardcoded)
- Do not depend on fixed booking IDs

**Steps:**
1. Navigate to a room's reservation page
2. Select check-in and check-out dates using the date picker
3. Fill in guest information (name, email, phone)
4. Submit the booking form
5. Verify booking confirmation or success state

**Expected Behavior:**
- Dates can be selected
- Guest information fields are fillable
- Booking form can be submitted
- A confirmation message or success state is displayed

---

## Page Object Model (POM) Requirements

### Pages to Generate

| Page Class       | Responsibility                              |
|------------------|---------------------------------------------|
| `BasePage`       | Common navigation, wait helpers             |
| `HomePage`       | Home page elements, room section discovery  |
| `RoomsPage`      | Room card discovery, room selection         |
| `BookingPage`    | Reservation form, date picker, guest fields |
| `AdminPage`      | Admin login form, dashboard verification    |

### POM Rules

- Each page class represents ONE meaningful application page/section
- Selectors must be derived from collected evidence — never invented
- Business actions exposed as methods (e.g., `select_available_room()`)
- No test logic inside page classes
- No hardcoded MCP reference IDs
- Tests read at a business level: `booking_page.fill_guest_details(guest)`

---

## Selector and Evidence Rules

- ALL selectors must originate from accessibility snapshot evidence
- Do NOT invent CSS selectors not observed in evidence
- Do NOT invent XPath not observed in evidence
- Prefer: ARIA roles, accessible names, data-testid attributes
- Fallback: Playwright locators derived from observed structure
- Document selector source in generated code comments

---

## Dynamic Data Rules

- Guest names: generated at runtime (e.g., Faker or simple random strings)
- Dates: calculated from `datetime.date.today()` — never hardcoded
- Room IDs: discovered from the application during exploration
- Booking IDs: captured from API/UI responses and passed between tests

---

## Scope Boundaries

**In Scope:**
- Home page validation
- Primary navigation
- Room discovery and selection
- Reservation page validation
- Admin login (positive and negative)
- Booking form submission

**Out of Scope:**
- Payment processing (not implemented in demo)
- Email verification
- Multi-language testing
- Performance/load testing
