from .base_page import BasePage


class HomePage(BasePage):
    def open(self):
        self.page.goto(self.base_url.rstrip("/"))
        self.page.wait_for_timeout(1500)

    def url(self):
        return self.page.url
