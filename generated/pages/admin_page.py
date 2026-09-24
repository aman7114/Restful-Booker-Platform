from playwright.sync_api import Page, expect
from pages.base_page import BasePage


class AdminPage(BasePage):
    def __init__(self, page: Page):
        super().__init__(page)
        self.username_input = self.page.get_by_placeholder("Enter username")
        self.password_input = self.page.get_by_label("Password")
        self.login_button = self.page.get_by_role("button", name="Login")
        self.logout_button = self.page.get_by_role("button", name="Logout")
        # Error alert uses ARIA role=alert
        self.error_alert = self.page.get_by_role("alert")

    def navigate_to_admin(self, base_url: str, admin_path: str):
        self.navigate(f"{base_url}{admin_path}")
        self.page.wait_for_load_state("networkidle")
        # May redirect to /admin/rooms if already logged in
        assert admin_path in self.page.url, (
            f"Expected URL to contain '{admin_path}', got: {self.page.url}"
        )

    def login(self, username: str, password: str):
        expect(self.username_input).to_be_visible(timeout=5000)
        self.username_input.fill(username)
        self.password_input.fill(password)
        self.login_button.click()

    def is_logged_in(self) -> bool:
        """True if the Logout button is visible."""
        try:
            self.logout_button.wait_for(state="visible", timeout=3000)
            return True
        except Exception:
            return False

    def ensure_logged_out(self):
        """If currently logged in, log out first."""
        if self.is_logged_in():
            self.logout_button.click()
            self.page.wait_for_load_state("networkidle")
