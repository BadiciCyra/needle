"""Program yöneticisi hesabı oluşturur (yönetici hesabı arayüzden açılamaz).

Kullanım (backend klasöründen):
    python -m seed.create_admin yonetici@ornek.org "Ad Soyad"

Şifre ekrandan sorulur; terminal geçmişinde kalmaması için komut satırı argümanı olarak alınmaz.
Etkileşimsiz ortamda (Docker, CI) NEEDLE_ADMIN_PASSWORD ortam değişkeni kullanılabilir.
"""

import getpass
import os
import sys

from sqlalchemy import select

from app.auth import hash_password
from app.db.models import User
from app.db.session import get_session_factory, init_db


def ensure_admin(email: str, password: str, name: str) -> str:
    """Yönetici hesabı yoksa oluşturur; varsa dokunmaz. Durumu anlatan tek satır döndürür."""
    email = email.strip().lower()
    if len(password) < 10:
        return "ADMIN_PASSWORD en az 10 karakter olmalı; yönetici hesabı oluşturulmadı."
    init_db()
    with get_session_factory()() as session:
        existing = session.scalar(select(User).where(User.email == email))
        if existing:
            if existing.role != "yonetici":
                return f"{email} başka bir rolle kayıtlı ({existing.role}); yönetici yapılmadı."
            return f"Yönetici hesabı zaten var: {email}"
        session.add(User(email=email, password_hash=hash_password(password), name=name.strip(), role="yonetici"))
        session.commit()
    return f"Yönetici hesabı oluşturuldu: {email}"


def main() -> None:
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    email, name = sys.argv[1].strip().lower(), sys.argv[2].strip()
    password = os.environ.get("NEEDLE_ADMIN_PASSWORD") or getpass.getpass("Şifre (en az 10 karakter): ")
    if len(password) < 10:
        sys.exit("Şifre en az 10 karakter olmalı.")

    init_db()
    with get_session_factory()() as session:
        if session.scalar(select(User).where(User.email == email)):
            sys.exit(f"{email} zaten kayıtlı.")
        session.add(User(email=email, password_hash=hash_password(password), name=name, role="yonetici"))
        session.commit()
    print(f"Yönetici hesabı oluşturuldu: {email}")


if __name__ == "__main__":
    main()
