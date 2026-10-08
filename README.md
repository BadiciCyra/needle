<div align="center">

# 🪡 Needle

**Needs & Leads için açık kaynak eşleştirme ve pilot takip platformu**

Kurumun dağınık ihtiyaç metnini yapılandırılmış bir brief'e çevirir, o brief'i uygun girişimlerle
**gerekçesiyle** eşleştirir ve eşleşme sonrası pilot sürecini ölçülebilir şekilde takip eder.

[![CI](https://github.com/BadiciCyra/needle/actions/workflows/ci.yml/badge.svg)](https://github.com/BadiciCyra/needle/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)
![Status](https://img.shields.io/badge/durum-geli%C5%9Ftirme%20a%C5%9Famas%C4%B1nda-orange)
![Zemin360](https://img.shields.io/badge/Zemin360-Hackathon%202026-8A2BE2)

</div>

---

## Problem

Bir kurumun inovasyon sorumlusu şunu yazıyor:

> "Sahadaki bayilerimizden gelen şikayetleri daha hızlı sınıflandırmak istiyoruz, çok manuel gidiyor."

Bu cümle bir girişim için kullanılamaz: kaç şikayet, hangi formatta, hangi sistemde, bütçe ne,
başarı kriteri ne? Bugün bu boşluğu bir insan dolduruyor. Program yöneticisi ihtiyacı deşifre
ediyor, kafasındaki listeden birkaç girişim çıkarıyor, tanıştırıyor ve pilotu Excel'de takip
ediyor. O kişi giderse bilgi de gidiyor.

**Asıl problem tanıştırmak değil, tanıştırdıktan sonra ne olduğunu bilmemek.**

## Nasıl çalışır

```mermaid
flowchart LR
    A["0 · Girdi<br/>Serbest ihtiyaç metni"] --> B["1 · Brief<br/>LLM yapılandırır,<br/>eksikse takip sorusu sorar"]
    B --> C["2 · Eşleştir<br/>Anlamsal benzerlik + filtre<br/>5 aday + 3 elenen, gerekçeli"]
    C --> D["3 · Pilot<br/>Kilometre taşları,<br/>hareketsizlik uyarısı"]
```

| Adım | Ne oluyor | Çıktı |
|---|---|---|
| **0 · Girdi** | Kurum ihtiyacını serbest metin olarak yazar | Dağınık, eksik bir paragraf |
| **1 · Brief'e çevir** | LLM metni yapılandırır; eksik alan varsa 2–3 takip sorusu sorar | Problem, kapsam, gereken yetkinlikler, süre, başarı kriteri |
| **2 · Eşleştir** | Brief embed edilir; profil havuzunda anlamsal benzerlik + filtre (sektör, olgunluk, lokasyon) | 5 uygun aday + 3 elenen aday, her biri gerekçesiyle |
| **3 · Pilotu takip et** | Eşleşme kabul edilince otomatik pilot kartı açılır | Kilometre taşları, durum, hareketsizlik uyarısı, haftalık özet |

## Neden farklı

Açık inovasyon platformu kategorisinde olgun ürünler var (Skipso, Innoget, Ambivation).
Needle'ın farkı kategori değil, **uyum**:

- **Gerekçeli eşleşme:** Her eşleşmede hangi cümlenin hangi yetkinlikle örtüştüğünün izi tutulur.
- **Negatif eşleşme:** "Yakındı ama olmadı, çünkü X" kaydı. Elenenler de gerekçesiyle saklanır.
- **Pilot erken uyarısı:** "12 gündür hareketsiz" uyarısı. Pilotlar sessizce ölmesin.
- **Türkçe ve açık kaynak:** Zemin360'ın Needs & Leads akışına göre kurgulandı, İSTKA raporlamasına doğrudan çıktı verecek şekilde tasarlandı.

## Teknoloji

| Katman | Seçim |
|---|---|
| LLM orkestrasyon | LangGraph + Gemini |
| Vektör arama | PostgreSQL + pgvector |
| Frontend | React + hazır component kütüphanesi |
| Dağıtım | Docker |

## Kapsam

Bilinçli olarak yalnızca yukarıdaki dört adım kodlanıyor. Mesajlaşma, bildirim, profil doğrulama,
rozet, sosyal ağ ve mobil uygulama [yol haritasında](#yol-haritası) duruyor.

## Yol haritası

- [ ] Veri modeli + brief üretimi (Adım 1)
- [ ] Eşleştirme motoru, gerekçeli skor ve negatif eşleşme (Adım 2)
- [ ] Pilot tracker (Adım 3)
- [ ] Demo modu (cache'li LLM cevapları)
- [ ] Kapalı döngü: pilot sonucunun sonraki eşleştirmelerin ağırlığına geri dönmesi
- [ ] İhtiyacı yazan birim ile ihtiyacı yaşayan saha birimini ayrıştırma

## Kurulum

Gereken: Docker Desktop. (Geliştirme için ayrıca Python 3.12+ ve Node 20+.)

1. `.env.example` dosyasını `.env` olarak kopyala ve `LLM_API_KEY` satırına bir Gemini API anahtarı yaz
   ([Google AI Studio](https://aistudio.google.com/apikey)). LLM katmanı herhangi bir OpenAI uyumlu uç noktayla
   çalışır; Ollama veya OmniRoute için `.env.example`'daki notlara bak.
2. Her şeyi başlat:

```bash
docker compose up -d --build
```

| Adres | Ne |
|---|---|
| http://localhost:3000 | Needle arayüzü |
| http://localhost:8000/docs | API dokümanı (`.env`'de `API_PORT` verildiyse o port) |

API ilk açılışta girişim tablosu boşsa `STARTUPS_FILE` dosyasındaki girişimleri (varsayılan:
[kaynaklı gerçek girişimler](backend/seed/startups_gercek.json)) embedding'leriyle yükler. İlk açılışta
embedding ve reranker modelleri indirildiği için birkaç dakika sürebilir.

### Hesaplar

Üç rol var:

| Rol | Nasıl açılır | Ne görür |
|---|---|---|
| **Firma** | Arayüzde "Hesap açın" → "Çözüm arıyorum" | Yalnızca kendi kurumunun ihtiyaçları, eşleşmeleri, tanıştırmaları, çağrıları ve pilotları. İlk girişte 3 adımlık firma profili doldurulur; sektör, şehir, olgunluk, bütçe ve süre bilgisi brief'in boş alanlarını tamamlar. |
| **Girişim** | Arayüzde "Hesap açın" → "Çözüm sunuyorum" | Havuzdaki profilini sahiplenir ya da yeni profil açar; program yöneticisi onaylar (şirket e-postasının sitenin alan adıyla eşleşip eşleşmediği onay listesinde görünür). E-posta doğrulaması eklenince `STARTUP_DOMAIN_AUTOVERIFY=true` ile eşleşenler anında doğrulanabilir. Doğrulandıktan sonra kendisine gelen tanıştırma isteklerini, açık çağrıları ve kendi pilotlarını görür; ihtiyaç listesine erişemez. |
| **Program yöneticisi** | Komut satırından (aşağıda) | Bütün kayıtlar; girişim hesaplarını onaylar, hesabı olmayan girişim adına tanıştırmaya cevap verir |

**Tanıştırma:** Firma eşleşmedeki bir adayı kabul edince girişime tanıştırma isteği gider; girişim kabul edince pilot
kartı açılır ve iki taraf aynı kartı görür (girişim kilometre taşı ekler, "işe yaradı mı" kararı kurumdadır).

**Program raporu** (yönetici → Rapor): ihtiyaçların pilota ve sonuca dönüşme akışı, sektörler, tanıştırma kabul oranı,
uygun girişim bulunamayan ihtiyaçlar ve havuzda eksik kalan yetkinlikler. "Excel indir" aynı veriyi Özet, Sektörler,
Eksik yetkinlikler, Uygun bulunamayan, Pilotlar ve Havuz sayfalarıyla verir.

**Açık çağrı:** Havuzda problemi doğrudan çözen girişim bulunamazsa ihtiyaç tek tıkla açık çağrıya çevrilir (kurum
adı gizlenebilir, son tarih verilebilir). Doğrulanmış girişimler başvurur; firma kabul edince pilot doğrudan açılır.

```bash
docker compose exec api python -m seed.create_admin yonetici@kurum.org "Ad Soyad"
```

Şifre ekrandan sorulur (komut geçmişinde kalmaz). Şifreler argon2 ile saklanır, oturum httpOnly çerezle taşınır.
Aynı e-postaya 15 dakikada 5 hatalı denemeden sonra giriş geçici olarak kilitlenir. "Şifremi unuttum" bağlantısı
e-postayla gider: `.env`'de SMTP ayarlanmadıysa bağlantı `docker compose logs api` çıktısına yazılır. Şifre
sıfırlanınca ya da değiştirilince diğer cihazlardaki oturumlar kapanır.

HTTPS arkasında yayına alınırken `.env`'de `COOKIE_SECURE=true` yapılmalı. Kayıt ekranındaki aydınlatma metni
bir taslaktır ve yayından önce hukuki inceleme gerektirir.

### Yayına alma (Dokploy + VPS)

Sunucuda en az 4 GB RAM gerekir (embedding modeli yüklüyken API ~1,2 GB kullanır). Dokploy'da **Compose** servisi
açılır, repo bağlanır ve compose yolu olarak `docker-compose.dokploy.yml` seçilir. Environment sekmesine:

```
POSTGRES_PASSWORD=<uzun rastgele şifre>
LLM_API_KEY=<Gemini anahtarı>
APP_BASE_URL=https://<domain>
COOKIE_SECURE=true
```

Domains sekmesinde `web` servisine, 80 numaralı porta domain bağlanır. İlk deploy imajları derler ve 282 girişimi
yükler (10–15 dk). Yönetici hesabı api konteynerinde `python -m seed.create_admin <e-posta> "<Ad>"` ile açılır.

### Geliştirme (Docker'sız API ve arayüz)

```bash
docker compose up -d db
pip install -r backend/requirements.txt
python -m uvicorn app.main:app --app-dir backend --port 8010
npm --prefix frontend install
npm --prefix frontend run dev        # http://localhost:5173, /api → 127.0.0.1:8010
```

Testler: `cd backend && python -m pytest`. GitHub Actions her PR'da backend testlerini (pgvector'lü Postgres ile, entegrasyon dahil) ve arayüz derlemesini çalıştırır. Uçtan uca API testi ayrı bir veritabanı ister
(test tabloları silip yeniden kurar): `NEEDLE_TEST_DATABASE_URL=postgresql+psycopg://needle:needle@127.0.0.1:5432/needle_test`.

## Katkı

Katkı rehberi için [CONTRIBUTING.md](CONTRIBUTING.md) dosyasına bak.

## Lisans

[Apache License 2.0](LICENSE)
