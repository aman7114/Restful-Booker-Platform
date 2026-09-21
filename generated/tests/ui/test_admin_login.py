def test_admin_login_success(admin_page):
    admin_page.open()
    admin_page.login("admin", "password")
    assert admin_page.is_logged_in()


def test_admin_login_failure(admin_page):
    admin_page.open()
    admin_page.login("admin", "wrong")
    assert not admin_page.is_logged_in()
