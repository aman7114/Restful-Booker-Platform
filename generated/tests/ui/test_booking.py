def test_browse_rooms(home_page):
    home_page.open()
    assert home_page.url().startswith("https://automationintesting.online")


def test_negative_contact_booking(booking_page):
    booking_page.open()
    booking_page.fill_contact_form("", "", "", "", "")
    assert booking_page.page_title()
