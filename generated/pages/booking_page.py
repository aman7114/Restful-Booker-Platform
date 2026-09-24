from playwright.sync_api import Page, expect
from pages.base_page import BasePage
import datetime


class BookingPage(BasePage):
    def __init__(self, page: Page):
        super().__init__(page)
        # Check Availability section (always on home page)
        self.check_availability_button = self.page.get_by_role(
            "button", name="Check Availability"
        )
        # Contact / Enquiry form (Send Us a Message section)
        self.name_input = self.page.get_by_role("textbox", name="Name")
        self.email_input = self.page.get_by_role("textbox", name="Email")
        self.phone_input = self.page.get_by_role("textbox", name="Phone")
        self.subject_input = self.page.get_by_role("textbox", name="Subject")
        # Message textarea has no accessible name
        self.message_textarea = self.page.locator("textarea").last
        self.submit_button = self.page.get_by_role("button", name="Submit")
        self.success_heading = self.page.get_by_role("heading").filter(
            has_text="Thanks for getting in touch"
        )

    def is_page_loaded(self) -> bool:
        expect(self.page).to_have_title("Restful-booker-platform demo")
        expect(self.check_availability_button).to_be_visible(timeout=10000)
        return True

    def calendar_controls_present(self) -> bool:
        expect(self.check_availability_button).to_be_visible(timeout=10000)
        return True

    def booking_form_fields_present(self) -> bool:
        expect(self.name_input).to_be_visible(timeout=10000)
        expect(self.email_input).to_be_visible(timeout=10000)
        expect(self.phone_input).to_be_visible(timeout=10000)
        expect(self.subject_input).to_be_visible(timeout=10000)
        expect(self.submit_button).to_be_visible(timeout=10000)
        return True

    def fill_and_submit(self, name: str, email: str, phone: str,
                        subject: str, message: str):
        self.name_input.fill(name)
        self.email_input.fill(email)
        self.phone_input.fill(phone)
        self.subject_input.fill(subject)
        self.message_textarea.fill(message)
        self.submit_button.click()
