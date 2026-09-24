from playwright.sync_api import Page, expect, Locator
from pages.base_page import BasePage


class RoomsPage(BasePage):
    def __init__(self, page: Page):
        super().__init__(page)
        self.our_rooms_heading = self.page.get_by_role("heading", name="Our Rooms")

    def get_book_now_links(self) -> Locator:
        """Return all 'Book now' links on the page."""
        return self.page.get_by_role("link", name="Book now")

    def get_room_count(self) -> int:
        return self.get_book_now_links().count()

    def click_first_room(self):
        link = self.get_book_now_links().first
        expect(link).to_be_visible(timeout=10000)
        link.click()
        self.page.wait_for_load_state("networkidle")
