from playwright.sync_api import Page, expect


class BasePage:
    def __init__(self, page: Page):
        self.page = page

    def navigate(self, url: str):
        self.page.goto(url, wait_until="domcontentloaded")

    def wait_for_load(self):
        self.page.wait_for_load_state("networkidle")
