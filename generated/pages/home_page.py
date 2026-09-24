from playwright.sync_api import Page, expect
from pages.base_page import BasePage


class HomePage(BasePage):
    def __init__(self, page: Page):
        super().__init__(page)
        self.heading = self.page.get_by_role("heading", name="Welcome to Shady Meadows B&B")
        self.rooms_heading = self.page.get_by_role("heading", name="Our Rooms")

    def get_navigation_links(self):
        return self.page.locator("nav a")

    def is_loaded(self) -> bool:
        expect(self.page).to_have_title("Restful-booker-platform demo")
        return True
