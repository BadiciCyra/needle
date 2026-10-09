"""Girişimlerin sitesinden iletişim e-postasını toplar ve startups_gercek.json'a yazar.

Her girişim için ana sayfa ve iletişim sayfaları (bağlantılardan bulunanlar ve /iletisim, /contact gibi tahminler)
okunur; mailto bağlantıları ve sayfa metnindeki adresler toplanır. Sitenin kendi alan adındaki adres tercih edilir,
genel kutular (info@, hello@, iletisim@ ...) öne alınır. Bulunan adres ve bulunduğu sayfa kayda yazılır:

    "iletisim": {"email": "info@ornek.com", "kaynak": "https://ornek.com/iletisim"}

Kullanım (backend klasöründen; yeniden çalıştırılabilir, yalnızca iletisim alanı güncellenir):
    python -m seed.iletisim_topla
"""

import json
import re
import ssl
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from html import unescape
from urllib.parse import unquote, urljoin, urlparse

from app.seed_data import SEED_DIR

SEED = SEED_DIR / "startups_gercek.json"
EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
MAILTO = re.compile(r"mailto:([^\"'?>\s]+)", re.I)
HREF = re.compile(r"href=[\"']([^\"'#]+)[\"']", re.I)
CONTACT_WORDS = ("iletisim", "iletişim", "contact", "bize-ulasin", "bize-ulaşın", "ulasin", "hakkimizda", "about")
GUESSES = ("/iletisim", "/contact", "/tr/iletisim", "/en/contact", "/contact-us", "/bize-ulasin")
PREFERRED = ("info", "hello", "merhaba", "iletisim", "contact", "bilgi", "sales", "satis", "business", "team")
JUNK = re.compile(r"\.(png|jpe?g|gif|svg|webp|css|js)$|example\.|sentry|wixpress|domain\.com|email\.com|yourdomain|@2x", re.I)
PLACEHOLDER = re.compile(r"@(company|sirket|şirket|quest|test|mail|firma|example)\.(com|com\.tr)$|^(info|test|ornek|örnek)@(gmail|hotmail)\.com$", re.I)
UA = "Mozilla/5.0 (compatible; NeedleBot/1.0; +iletisim toplama)"
_ctx = ssl.create_default_context()


def fetch(url: str) -> str:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "tr,en;q=0.8"})
        with urllib.request.urlopen(req, timeout=12, context=_ctx) as r:
            if "text/html" not in r.headers.get("Content-Type", "text/html"):
                return ""
            return r.read(600_000).decode(r.headers.get_content_charset() or "utf-8", "replace")
    except Exception:
        return ""


def domain(url: str) -> str:
    return urlparse(url).netloc.lower().removeprefix("www.")


def emails_in(html: str) -> list[str]:
    text = unescape(html).replace("[at]", "@").replace("(at)", "@")
    found = [unquote(m).strip().lower() for m in MAILTO.findall(text)] + [m.lower() for m in EMAIL.findall(text)]
    found = [e.rstrip(".") for e in found]
    return [e for e in found if EMAIL.fullmatch(e) and not JUNK.search(e) and not PLACEHOLDER.search(e)]


def best(emails: list[tuple[str, str]], site: str) -> tuple[str, str] | None:
    """(adres, sayfa) çiftlerinden sitenin alan adındaki en uygun genel kutuyu seçer."""
    site_domain = domain(site)

    def score(item):
        email = item[0]
        local, _, host = email.partition("@")
        same = host == site_domain or host.endswith("." + site_domain) or site_domain.endswith("." + host)
        generic = next((i for i, p in enumerate(PREFERRED) if local.startswith(p)), len(PREFERRED))
        return (not same, generic, len(email))

    candidates = sorted(set(emails), key=score)
    return candidates[0] if candidates else None


def collect(item: dict) -> dict | None:
    site = item["kaynak"][0]
    home = fetch(site)
    pages = [(site, home)]
    links = {urljoin(site, h) for h in HREF.findall(home) if any(w in h.lower() for w in CONTACT_WORDS)}
    links = [u for u in links if domain(u) == domain(site)][:4] or [urljoin(site, g) for g in GUESSES[:3]]
    pages += [(u, fetch(u)) for u in links]
    found = [(e, url) for url, html in pages for e in emails_in(html)]
    choice = best(found, site)
    return {"email": choice[0], "kaynak": choice[1]} if choice else None


def main() -> None:
    data = json.loads(SEED.read_text(encoding="utf-8"))
    with ThreadPoolExecutor(12) as pool:
        results = list(pool.map(collect, data))
    for item, contact in zip(data, results):
        if contact:
            item["iletisim"] = contact
        else:
            item.pop("iletisim", None)
    SEED.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    found = sum(1 for r in results if r)
    print(f"{found}/{len(data)} girişimde e-posta bulundu")
    missing = [i["name"] for i, r in zip(data, results) if not r]
    print("Bulunamayanlar:", ", ".join(missing[:40]) + (" ..." if len(missing) > 40 else ""), file=sys.stderr)


if __name__ == "__main__":
    main()
