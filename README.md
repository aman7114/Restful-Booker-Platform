# AI QA Automation — Restful Booker Platform

An evidence-driven, AI-generated QA automation framework that explores, generates, executes, and reports — fully automatically with a single command.

```bash
python main.py
```

---

## What It Does

```
SPECIFICATION
      │
      ▼
EXPLORATION (Playwright MCP + requests)
      │
      ▼
   EVIDENCE
      │
      ▼
   GEMINI (Test Generation)
      │
      ▼
GENERATED POM + TESTS
      │
      ▼
    PYTEST
      │
      ▼
EXECUTION EVIDENCE
      │
      ▼
   GEMINI (Report Generation)
      │
      ▼
  QA REPORT
```

---

## Architecture

```
project_root/
│
├── .env                    ← Your configuration (DO NOT COMMIT)
├── .env.example            ← Template for .env
├── requirements.txt        ← Project dependencies
├── README.md               ← This file
├── main.py                 ← ONLY entry point
├── ui.md                   ← UI testing specification
├── api.md                  ← API testing specification
├── spec.md                 ← Master AI generation contract
│
├── generation/             ← Implementation modules (one concern each)
│   ├── config.py           ← .env loading and validation
│   ├── mcp_client.py       ← Playwright MCP communication
│   ├── ui_generator.py     ← UI exploration and evidence collection
│   ├── api_generator.py    ← API exploration and evidence collection
│   ├── test_generator.py   ← Gemini test generation
│   ├── executor.py         ← pytest execution and result collection
│   └── report_generator.py ← Gemini QA report generation
│
├── evidence/               ← Runtime-collected evidence
│   ├── ui/                 ← UI snapshots, screenshots, element data
│   └── api/                ← API response data, endpoint evidence
│
└── generated/              ← AI-generated automation project
    ├── conftest.py
    ├── pytest.ini
    ├── pages/              ← Page Object Model classes
    ├── tests/
    │   ├── ui/             ← UI tests (Playwright + pytest)
    │   └── api/            ← API tests (requests + pytest)
    └── reports/
        ├── html/           ← pytest-html report
        ├── junit.xml       ← JUnit XML results
        ├── execution.json  ← Structured execution data
        └── report.md       ← AI-generated QA report
```

---

## Prerequisites

- **Python 3.11+**
- **Node.js 18+** (required for Playwright MCP via npx)
- **A Gemini API key** from [Google AI Studio](https://aistudio.google.com/)
- Internet access to `automationintesting.online`

---

## Installation

```bash
# 1. Clone or create the project directory
cd "Automation Project"

# 2. Create a virtual environment
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # Linux/macOS

# 3. Install dependencies
pip install -r requirements.txt

# 4. Install Playwright browsers
playwright install chromium

# 5. Configure your environment
copy .env.example .env
# Edit .env with your Gemini API key and credentials
```

---

## .env Configuration

All configuration is in `.env`. Never hardcode values in Python files.

```env
# Required — get from https://aistudio.google.com/
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-2.0-flash

# Application URLs
UI_BASE_URL=https://automationintesting.online
API_BASE_URL=https://automationintesting.online/api

# Admin credentials (for admin login tests)
ADMIN_USERNAME=admin
ADMIN_PASSWORD=password
ADMIN_PATH=/admin

# Playwright MCP (defaults work for most setups)
MCP_COMMAND=npx
MCP_PACKAGE=@playwright/mcp@latest

# Browser settings
HEADLESS=true

# Timeouts
API_TIMEOUT=30
UI_EVIDENCE_TIMEOUT=10000
UI_POLL_INTERVAL=1000
```

---

## How It Works

### 1. How MCP Works

[Playwright MCP](https://github.com/microsoft/playwright-mcp) is a Model Context Protocol server that exposes Playwright browser automation as MCP tools.

`generation/mcp_client.py` starts `npx @playwright/mcp@latest` as a subprocess and communicates with it over stdio. This allows the framework to:
- Navigate to URLs
- Capture accessibility snapshots (the full accessibility tree)
- Take screenshots
- Click elements
- Fill form fields

The accessibility snapshot is the key output — it describes every element on the page in a structured text format, which is used for evidence collection.

### 2. How Evidence is Collected

**UI Evidence** (`generation/ui_generator.py`):
- Navigates through 6 UI workflows
- Captures accessibility snapshots at each step
- Parses headings, buttons, links, textboxes from snapshots
- Discovers room cards dynamically (no hardcoded room names)
- Records all discovered elements, URLs, and navigation paths
- Saves everything to `evidence/ui/*.json`

**API Evidence** (`generation/api_generator.py`):
- Uses `requests` to call each endpoint
- Records request payload, status code, response headers, response body
- Covers positive and negative scenarios
- Generates all test data at runtime (no hardcoded values)
- Saves everything to `evidence/api/*.json`

### 3. How Gemini Generates Tests

`generation/test_generator.py` sends **one Gemini request** containing:
- `spec.md` — what to generate
- `ui.md` — UI workflows and rules
- `api.md` — API endpoints and scenarios
- All UI evidence files
- All API evidence files

Gemini returns a JSON object:
```json
{
  "files": [
    {"path": "pages/home_page.py", "content": "..."},
    {"path": "tests/ui/test_home.py", "content": "..."}
  ]
}
```

Each file is validated and written to `generated/`.

### 4. How POM is Generated

The Page Object Model follows this pattern:
- `BasePage` — common actions (navigate, wait)
- `HomePage`, `RoomsPage`, `BookingPage`, `AdminPage` — page-specific locators and business actions
- Selectors are derived from accessibility evidence, not invented
- Test logic stays in test files, not page classes

### 5. How Tests Execute

```bash
cd generated && pytest tests/ --html=reports/html/report.html --junitxml=reports/junit.xml
```

You can run the generated project directly after it has been created. Every pytest run also refreshes `reports/report.md` locally from the executed results, so no Gemini/API token is used for repeat test runs.
Results are captured in the HTML and JUnit reports, and the Markdown report is generated by the pytest hook in `generated/pytest_report_hook.py`.

### 6. How Report Generation Works

`generation/report_generator.py` sends **one Gemini request** containing:
- `execution.json` (test results)
- UI and API evidence summaries
- The specification context

Gemini generates a professional QA report in Markdown with:
- Executive Summary
- Test Execution Summary
- UI/API Results
- Failure Analysis (facts vs. AI inferences clearly labeled)
- Coverage Summary
- Recommendations

---

## Running

```bash
python main.py
```

For repeat test runs without regenerating the project or spending API tokens:

```bash
cd generated && pytest
```

That's it. The framework handles everything automatically.

---

## Output

After a successful run:

| Output | Location |
|--------|----------|
| UI evidence | `evidence/ui/` |
| API evidence | `evidence/api/` |
| Generated POM | `generated/pages/` |
| Generated tests | `generated/tests/` |
| HTML test report | `generated/reports/html/report.html` |
| JUnit XML | `generated/reports/junit.xml` |
| Execution data | `generated/reports/execution.json` |
| Markdown QA report | `generated/reports/report.md` |
| AI QA report | `generated/reports/report.md` |

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `Missing required environment variables` | Copy `.env.example` to `.env` and fill in values |
| `Playwright MCP startup failed` | Ensure Node.js 18+ is installed and `npx` works |
| `Test generation failed` | Check `GEMINI_API_KEY` is valid and model name is correct |
| `No tests collected` | Check `generated/tests/` exists and has test files |
| MCP hangs | Check network access to `automationintesting.online` |
