"""Girişim sitelerinden iletişim adresi toplama: ağa çıkmadan ayrıştırma ve seçim kuralları."""

from seed.iletisim_topla import best, emails_in


def test_mailto_is_decoded_and_non_addresses_are_dropped():
    html = '<a href="mailto:info%40ornek.com">Yaz</a> <a href="mailto:iletisim">İletişim</a> logo@2x.png bilgi[at]ornek.com'
    assert emails_in(html) == ["info@ornek.com", "bilgi@ornek.com"]


def test_form_placeholders_are_not_contacts():
    assert emails_in("you@company.com ornek@sirket.com info@gmail.com satis@gercek.com.tr") == ["satis@gercek.com.tr"]


def test_prefers_generic_inbox_on_the_sites_own_domain():
    found = [("ali.veli@ornek.com", "a"), ("info@ornek.com", "b"), ("info@ajans.com", "c")]
    assert best(found, "https://www.ornek.com/tr") == ("info@ornek.com", "b")
    assert best([], "https://ornek.com") is None
