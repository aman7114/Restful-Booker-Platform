from .base_page import BasePage


class AdminPage(BasePage):
    username_selector = '#username'
    password_selector = '#password'
    login_selector = '#doLogin'
    logout_selector = 'button[type="submit"]'

    def open(self):
        self.page.goto(self.base_url.rstrip("/") + '/admin/')
        self.page.wait_for_timeout(1500)

    def login(self, username="admin", password="password"):
        if not all((self.username_selector, self.password_selector, self.login_selector)):
            raise RuntimeError("Admin login controls were not uniquely observed by Playwright MCP.")
        self.page.locator(self.username_selector).fill(username)
        self.page.locator(self.password_selector).fill(password)
        self.page.locator(self.login_selector).click()
        self.page.wait_for_timeout(1500)

    def is_logged_in(self):
        # The admin SPA can keep the same URL after authentication and may not
        # render a logout control in the initial DOM evidence. The username
        # control is observed before login, so use its post-login visibility as
        # the deterministic state signal: visible form => still logged out;
        # hidden/removed form => authenticated.
        if self.username_selector:
            locator = self.page.locator(self.username_selector)
            if locator.count() == 0:
                return True
            try:
                return not locator.first.is_visible()
            except Exception:
                return False
        if self.logout_selector:
            return self.page.locator(self.logout_selector).count() > 0
        return False

    def logout(self):
        if not self.logout_selector:
            raise RuntimeError("Logout control was not observed by Playwright MCP.")
        self.page.locator(self.logout_selector).click()
