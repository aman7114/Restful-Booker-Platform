from .base_page import BasePage


class BookingPage(BasePage):
    contact_name_selector = '#name'
    contact_email_selector = '#email'
    contact_phone_selector = '#phone'
    contact_subject_selector = '#subject'
    contact_description_selector = '#description'
    contact_submit_selector = '#subject'

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
