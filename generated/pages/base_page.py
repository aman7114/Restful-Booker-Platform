from playwright.sync_api import Page


class BasePage:
    def __init__(self, page: Page, base_url: str):
        self.page = page
        self.base_url = base_url

    def open(self, path: str = "/"):
        self.page.goto(self.base_url.rstrip("/") + path)
        self.page.wait_for_load_state("domcontentloaded")
