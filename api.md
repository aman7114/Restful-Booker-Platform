# API Testing Specification
# Restful Booker Platform — REST API

## API Base URL

Defined in .env as `API_BASE_URL`
Default: `https://automationintesting.online/api`

---

## Authentication

The API uses token-based authentication for protected endpoints.

### POST /auth/login

Obtain an authentication token.

**Request Body:**
```json
{
  "username": "<from .env ADMIN_USERNAME>",
  "password": "<from .env ADMIN_PASSWORD>"
}
```

**Positive Response (200):**
```json
{
  "token": "<string>"
}
```

**Negative Response (403):**
```json
{
  "reason": "Bad credentials"
}
```

**Test Scenarios:**

| Scenario | Input | Expected |
|----------|-------|----------|
| Valid credentials | Correct username/password | 200 + token |
| Invalid password | Correct username, wrong password | 403 |
| Invalid username | Wrong username | 403 |
| Empty credentials | Empty strings | 403 |

The token must be captured and reused for authenticated API requests.
Do NOT hardcode the token.

---

## Rooms API

### GET /room

Retrieve all rooms.

**Authentication:** Not required (public endpoint)

**Response (200):**
```json
{
  "rooms": [
    {
      "roomid": <integer>,
      "roomName": "<string>",
      "type": "<Single|Double|Twin|Family|Suite>",
      "accessible": <boolean>,
      "image": "<url>",
      "description": "<string>",
      "features": ["<string>"],
      "roomPrice": <integer>
    }
  ]
}
```

**Test Scenarios:**

| Scenario | Expected |
|----------|----------|
| Get all rooms | 200 + rooms array |
| Response structure | Each room has roomid, roomName, type, roomPrice |
| Non-empty | At least one room returned |

### GET /room/{id}

Retrieve a specific room by ID.

**Authentication:** Not required

**Test Scenarios:**

| Scenario | Expected |
|----------|----------|
| Valid room ID | 200 + room object |
| Invalid room ID (e.g. 99999) | 404 or appropriate error |

---

## Bookings API

### POST /booking

Create a new booking.

**Authentication:** Required (token in cookie or Authorization header)

**Request Body:**
```json
{
  "roomid": <integer>,
  "firstname": "<string>",
  "lastname": "<string>",
  "depositpaid": <boolean>,
  "email": "<email>",
  "phone": "<10+ digit string>",
  "bookingdates": {
    "checkin": "<YYYY-MM-DD>",
    "checkout": "<YYYY-MM-DD>"
  }
}
```

**Rules:**
- Dates must be valid and in the future (calculated at runtime)
- checkout must be after checkin
- roomid must reference an existing room (discovered via GET /room)
- firstname, lastname, email, phone: generate dynamically at runtime

**Positive Response (201):**
```json
{
  "bookingid": <integer>,
  "booking": {
    "roomid": <integer>,
    "firstname": "<string>",
    "lastname": "<string>",
    ...
  }
}
```

**Test Scenarios:**

| Scenario | Expected |
|----------|----------|
| Valid booking | 201 + bookingid |
| Missing required field | 400 or 422 |
| Invalid date range (checkout before checkin) | 400 or 422 |
| Invalid roomid | 400 or 404 |

The `bookingid` from the creation response must be captured and used in
subsequent read/update/delete tests.

### GET /booking

Retrieve all bookings.

**Authentication:** Required

**Response (200):**
```json
{
  "bookings": [
    {
      "bookingid": <integer>
    }
  ]
}
```

### GET /booking/{id}

Retrieve a specific booking.

**Authentication:** Required

**Test Scenarios:**

| Scenario | Expected |
|----------|----------|
| Valid booking ID (created in same test run) | 200 + booking object |
| Invalid booking ID | 404 |

### PUT /booking/{id}

Update an existing booking.

**Authentication:** Required

**Request Body:** Same structure as POST /booking

**Test Scenarios:**

| Scenario | Expected |
|----------|----------|
| Valid update | 200 + updated booking |
| Unauthorized (no token) | 403 |

### DELETE /booking/{id}

Delete a booking.

**Authentication:** Required

**Test Scenarios:**

| Scenario | Expected |
|----------|----------|
| Valid delete (booking created in same run) | 202 or 204 |
| Already deleted | 404 |
| Unauthorized | 403 |

---

## API Workflow Relationships

The tests must follow this dependency chain:

```
POST /auth/login         → token
GET /room                → roomid
POST /booking            → bookingid (uses roomid from GET /room)
GET /booking/{id}        → verify created booking
PUT /booking/{id}        → update booking
DELETE /booking/{id}     → cleanup
```

Token and bookingid must be shared between tests via pytest fixtures.
Do NOT hardcode any IDs.

---

## Negative Test Scenarios

All negative scenarios should be isolated (not dependent on prior state).

| Test | Description |
|------|-------------|
| Auth with bad credentials | Expect 403 |
| GET room with invalid ID | Expect 404 |
| POST booking without token | Expect 403 |
| POST booking with missing fields | Expect 4xx |
| GET booking with invalid ID | Expect 404 |
| DELETE booking without token | Expect 403 |

---

## General API Rules

- All tests use `requests` library
- Base URL comes from config (never hardcoded)
- Auth token obtained via fixture and shared
- Runtime-generated data for names, dates, emails, phones
- Response validation covers: status code + key fields in response body
- Tests are independent where possible; share only fixture-managed state
