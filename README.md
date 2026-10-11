<div align="center">

# 🪡 Needle

**Kurum ihtiyaçlarını girişimlerle gerekçesiyle eşleştiren ve pilotu sonuna kadar takip eden açık kaynak platform**

Kurumun dağınık ihtiyaç metnini yapılandırılmış bir brief'e çevirir, girişim havuzundan problemi **doğrudan çözen**
adayları gerekçesi ve kanıtıyla bulur, tanıştırmadan pilotun kapanış değerlendirmesine kadar süreci tek yerde tutar.

[![CI](https://github.com/BadiciCyra/needle/actions/workflows/ci.yml/badge.svg)](https://github.com/BadiciCyra/needle/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)
![Status](https://img.shields.io/badge/durum-geli%C5%9Ftirme%20a%C5%9Famas%C4%B1nda-orange)
![Zemin360](https://img.shields.io/badge/Zemin360-Hackathon%202026-8A2BE2)

[Problem](#problem) · [Ne yapar](#ne-yapar) · [Eşleştirme nasıl çalışır](#eşleştirme-nasıl-çalışır) · [Kurulum](#kurulum) · [Yayına alma](#yayına-alma) · [Geliştirme](#geliştirme)

</div>

<p align="center">
  <img src="docs/ekran/eslestirme.png" alt="Eşleştirme sonucu: brief, gerekçeli kısa liste ve her adayın kanıt izleri" width="900">
  <br><sub>Serbest metinden çıkarılan brief ve gerekçeli kısa liste. Her kanıt, ihtiyaçtaki bir ifadeyi girişimin bir yetkinliğine bağlar.</sub>
</p>

---

## Problem

Bir kurumun inovasyon sorumlusu şunu yazıyor:

> "Sahadaki bayilerimizden gelen şikayetleri daha hızlı sınıflandırmak istiyoruz, çok manuel gidiyor."

Bu cümle bir girişim için kullanılamaz: kaç şikayet, hangi formatta, hangi sistemde, bütçe ne, başarı kriteri ne?
Bugün bu boşluğu bir insan dolduruyor. Program yöneticisi ihtiyacı deşifre ediyor, aklındaki listeden birkaç girişim
çıkarıyor, tanıştırıyor ve pilotu Excel'de takip ediyor. O kişi giderse bilgi de gidiyor.

**Asıl problem tanıştırmak değil, tanıştırdıktan sonra ne olduğunu bilmemek.**

## Ne yapar

```mermaid
flowchart LR
    A["İhtiyaç<br/>serbest metin"] --> B["Brief<br/>LLM yapılandırır,<br/>eksikse soru sorar"]
    B --> C["Eşleştirme<br/>gerekçeli kısa liste<br/>+ yakındı ama olmadı"]
    C --> D["Tanıştırma<br/>e-posta taslağı,<br/>girişim kabul eder"]
    D --> E["Pilot<br/>plan, hedefler,<br/>kilometre taşları"]
    E --> F["Kapanış<br/>işe yaradı mı,<br/>sonraki adım"]
    C -.->|uygun girişim yoksa| G["Açık çağrı<br/>girişimler başvurur"]
    G --> E
```

Üç rol var; her biri yalnızca kendi kayıtlarını görür.

**Firma (çözüm arayan kurum)**
- İhtiyacını kendi cümleleriyle yazar. Needle onu brief'e çevirir; eksik alan varsa en fazla 3 takip sorusu sorar.
- Gerekçeli kısa listeyi görür: hangi cümlesinin girişimin hangi yetkinliğiyle örtüştüğü ve elenenlerin neden elendiği.
- Adayı kabul edince tanıştırma isteği gider. Girişimin platformda hesabı yoksa iletişim adresiyle bir e-posta taslağı hazırlanır; firma düzenleyip kendisi gönderir.
- Havuzdaki herhangi bir girişimden de doğrudan tanışma isteyebilir. Sorun listede yoksa kendisi yazar.
- Uygun girişim çıkmazsa ihtiyacı tek tıkla **açık çağrıya** çevirir (kurum adı gizlenebilir).
- Genel bakışta tanıtımına ve ihtiyaçlarına göre **size uygun girişimler** listesi var.

**Girişim (çözüm sunan)**
- Havuzdaki profilini sahiplenir ya da yeni profil açar; program yöneticisi onaylar.
- Onaydan önce de kurumları, ne iş yaptıklarını ve açık çağrıları inceleyebilir.
- Ana sayfada **size uygun** bölümü: yetkinliklerine en yakın açık çağrılar ("sizin X yetkinliğiniz ↔ aranan Y" gerekçesiyle), kurumlar ve **talep sinyalleri**. Talep sinyali, son dört ayda en az iki farklı kurumun aradığı yetkinliktir; kurum adı gösterilmez.
- Tanıştırma isteklerine cevap verir, çağrılara başvurur, pilotlarını kurumla birlikte yürütür.

**Program yöneticisi**
- Girişim hesaplarını onaylar. Hesabı olmayan girişim adına tanıştırmaya cevap verir.
- **Program raporu:** İhtiyaçların pilota ve sonuca dönüşme oranı, sektörler, tanıştırma kabul oranı, uygun girişim bulunamayan ihtiyaçlar ve havuzda eksik kalan yetkinlikler. "Excel indir" aynı veriyi Özet, Sektörler, Eksik yetkinlikler, Uygun bulunamayan, Pilotlar ve Havuz sayfalarıyla verir.

<p align="center">
  <img src="docs/ekran/genel-bakis.png" alt="Firma genel bakışı: süreç özeti ve size uygun girişimler" width="900">
  <br><sub>Firma genel bakışı: açık işler, son ihtiyaçlar ve tanıtıma göre size uygun girişimler.</sub>
</p>

### Pilot

Tanıştırma kabul edilince ya da çağrı başvurusu onaylanınca pilot açılır ve iki taraf aynı sayfayı görür.

| Bölüm | İçerik |
|---|---|
| **Plan** | Amaç, kapsam, tarihler ve iki tarafın sorumluları. Pilot açılınca brief'ten önerilir; süre brief'teki metinden hesaplanır ("3 ay" → 90 gün). |
| **Hedefler** | Ne başarılacağı ve son tarihi. İki taraf da "tuttu" ya da "tutmadı" diye işaretler; tarihi geçen hedef öne çıkar. İlk hedef brief'teki başarı kriteridir. |
| **Kilometre taşları** | Sorumlu tarafı belli adımlar (kurum, girişim, ortak). Beş adımlık plan otomatik önerilir; geciken adım işaretlenir. |
| **Güncellemeler** | İki tarafın notları ve pilottaki her değişiklik zaman sırasıyla. Belli bir süre hareket olmayan pilot "hareketsiz" uyarısı alır. |
| **Kapanış** | Kurum: işe yaradı mı, sonraki adım (satın alma, genişletme, yeni pilot, bitirme), girişime 1–5 puan. Girişim: kendi değerlendirmesi ve iş birliği puanı. |

<p align="center">
  <img src="docs/ekran/pilot.png" alt="Pilot sayfası: plan, hedefler, kilometre taşları, güncellemeler ve kapanış değerlendirmesi" width="900">
  <br><sub>Pilot sayfası: iki taraf aynı planı, hedefleri ve güncelleme akışını görür.</sub>
</p>

## Eşleştirme nasıl çalışır

```mermaid
flowchart TD
    A["Brief"] --> B["Çoklu sorgu<br/>brief'in tamamı + her aranan yetkinlik"]
    B --> C["pgvector kosinüs araması<br/>her sorgu için en yakın 40"]
    C --> D["RRF ile birleştirme"]
    D --> E{"Havuz yeterli mi?<br/>en az 8 aday"}
    E -->|hayır| F["Filtre gevşet<br/>önce lokasyon, sonra olgunluk"] --> C
    E -->|evet| G["LLM puanlama<br/>her aday 0–10"]
    G --> H["Doğrudan çözüm denetimi<br/>en iyi 8 aday, 3 soru, 3 paralel oy"]
    H --> I["Güven eşiği<br/>kısa liste ≤ 5 + yakındı ama olmadı"]
    I --> J["Gerekçe ve kanıt kontrolü"]
```

1. **Çoklu sorgu ve RRF.** Brief'in tamamı ve her aranan yetkinlik ayrı birer sorgu olarak aranır. Sonuçlar ham skorla değil sırayla (Reciprocal Rank Fusion) birleştirilir. Böylece birden çok açıdan uygun çıkan aday, tek bir kısa sorguda yüksek skor alanın önüne geçer.
2. **Dinamik gevşetme.** Lokasyon ve olgunluk filtreleri yeterli aday bırakmazsa adım adım gevşetilir. Gevşetilmiş filtreyle gelen adaya küçük bir ceza uygulanır ve kartında not olarak gösterilir.
3. **LLM puanlama.** Adaylar ihtiyaca göre 0–10 arası puanlanır. Sıralamayı belirleyen bu puandır; kosinüs yalnızca adayları toplamaya yarar.
4. **Doğrudan çözüm denetimi.** En iyi 8 aday için üç soru sorulur: aynı nesneyle mi çalışıyor, aynı işi mi yapıyor, başka alana uyarlanması gerekiyor mu? Cevap ancak evet / evet / hayır ise aday "doğrudan çözüyor" sayılır. Kararsızlığı azaltmak için denetim 3 kez paralel çalışır ve çoğunluk oyu geçer.
5. **Güven eşiği.** Kısa liste sabit sayıyla değil kaliteyle kesilir. Doğrudan çözmeyen aday alınmaz. En iyi aday tabanın altındaysa "uygun girişim yok" denir ve en yakın adaylar "yakındı ama X eksik" gerekçesiyle gösterilir.
6. **Kanıt kontrolü.** LLM her aday için gerekçe yazar ve brief'ten bir ifadeyi girişimin bir yetkinliğiyle eşleştirir. Her kanıt üç kontrolden geçmek zorundadır: yetkinlik profilde birebir var mı, ifade brief'te gerçekten geçiyor mu, ikisi anlamca yeterince yakın mı? Geçemeyen kanıt atılır.

Her eşleştirme turunun izi (hangi turda kaç aday geldi, hangi filtre gevşedi, kaç kanıt elendi) kaydedilir ve arayüzde gösterilir.

## Neden farklı

Açık inovasyon platformu kategorisinde olgun ürünler var (Skipso, Innoget, Ambivation). Needle'ın farkı kategori değil, **uyum**:

- **Gerekçeli ve kanıtlı eşleşme:** Her eşleşmede hangi cümlenin hangi yetkinlikle örtüştüğü izlenir; uydurma kanıt kodla elenir.
- **"Uygun yok" diyebilmek:** Güven eşiği zayıf adayları kısa listeye sokmaz. Elenenler de gerekçesiyle saklanır.
- **Pilot sonuna kadar:** Plan, hedef, kilometre taşı ve kapanış değerlendirmesi tek sayfada; hareketsiz pilot uyarı alır.
- **İki yönlü:** Firma uygun girişimi, girişim uygun çağrıyı ve kurumu aynı vektör uzayında görür.
- **Türkçe ve açık kaynak:** Zemin360'ın Needs & Leads akışına göre kurgulandı; program raporu Excel olarak alınır.

## Teknoloji

| Katman | Seçim |
|---|---|
| API | FastAPI, SQLAlchemy 2 |
| LLM orkestrasyonu | LangGraph; OpenAI uyumlu uç nokta üzerinden Gemini 2.5 Flash (Ollama vb. ile de çalışır) |
| Embedding | `paraphrase-multilingual-MiniLM-L12-v2` (384 boyut, yerelde çalışır) |
| Vektör arama | PostgreSQL 16 + pgvector |
| Arayüz | React 19, TypeScript, Mantine 9, Vite |
| Dağıtım | Docker Compose (yerel), Dokploy ya da nginx arkasında VPS |
| CI | GitHub Actions: pgvector'lü Postgres ile backend testleri ve arayüz derlemesi |

Girişim havuzu, kaynağı belirtilmiş 282 gerçek girişimle gelir ([`startups_gercek.json`](backend/seed/startups_gercek.json)).

## Kurulum

Gereken: Docker Desktop ve bir Gemini API anahtarı ([Google AI Studio](https://aistudio.google.com/apikey)).

```bash
cp .env.example .env
```

`.env` dosyasında `LLM_API_KEY` satırını doldurun, sonra başlatın:

```bash
docker compose up -d --build
```

| Adres | Ne |
|---|---|
| http://localhost:3000 | Needle arayüzü |
| http://localhost:8000/docs | API dokümanı (`.env`'de `API_PORT` verildiyse o port) |

İlk açılışta girişim havuzu embedding'leriyle veritabanına yüklenir ve model indirilir; birkaç dakika sürebilir.
API her yeniden başladığında ilk embedding isteği modeli belleğe yükler, o istek 20–30 saniye sürebilir.

### Önemli ayarlar

| Değişken | Ne işe yarar |
|---|---|
| `LLM_API_KEY`, `LLM_MODEL`, `LLM_BASE_URL` | LLM bağlantısı. Herhangi bir OpenAI uyumlu uç nokta olabilir. |
| `RERANK_BACKEND` | `llm` (önerilen), `cross_encoder` (yerel model) ya da `none` (yalnızca vektör skoru) |
| `ADMIN_EMAIL`, `ADMIN_PASSWORD` | Doluysa açılışta program yöneticisi hesabı oluşturulur; hesap varsa dokunulmaz. |
| `COOKIE_SECURE` | HTTPS arkasında `true` olmalı. |
| `APP_BASE_URL`, `SMTP_*` | Şifre sıfırlama e-postası. SMTP boşsa bağlantı API loguna yazılır. |
| `DEMO_MODE` | `record` LLM cevaplarını kaydeder, `replay` onları tekrar oynatır (internetsiz demo). |
| `STARTUP_DOMAIN_AUTOVERIFY` | `true` olursa e-posta alan adı sitesiyle eşleşen girişim onaysız doğrulanır. |

Tamamı ve açıklamaları [`.env.example`](.env.example) dosyasında.

### Program yöneticisi hesabı

İki yol var:

- `.env` içine `ADMIN_EMAIL` ve `ADMIN_PASSWORD` (en az 10 karakter) yazıp API'yi yeniden başlatmak.
- Konsoldan açmak. Bu yolda şifre ekrandan sorulur ve komut geçmişinde kalmaz:

```bash
docker compose exec api python -m seed.create_admin yonetici@kurum.org "Ad Soyad"
```

Firma ve girişim hesapları arayüzden açılır ("Çözüm arıyorum" / "Çözüm sunuyorum").

### Güvenlik

- Şifreler argon2 ile saklanır, oturum httpOnly çerezle taşınır.
- Aynı e-postaya 15 dakikada 5 hatalı denemeden sonra giriş geçici olarak kilitlenir.
- Şifre sıfırlanınca ya da değiştirilince diğer cihazlardaki oturumlar kapanır.
- Firma yalnızca kendi kurumunun kayıtlarını görür; başka kurumun kaydı için 404 döner.

Kayıt ekranındaki aydınlatma metni bir taslaktır ve yayından önce hukuki inceleme gerektirir.

## Yayına alma

Sunucuda en az 4 GB RAM gerekir; embedding modeli yüklüyken API yaklaşık 1,2 GB kullanır. Sunucu için
[`docker-compose.dokploy.yml`](docker-compose.dokploy.yml) kullanılır: hiçbir portu dışarı açmaz ve veritabanı şifresini
ortamdan alır. `.env` dosyasına en az şunlar girilir:

```
POSTGRES_PASSWORD=<uzun rastgele şifre>
LLM_API_KEY=<Gemini anahtarı>
APP_BASE_URL=https://<domain>
COOKIE_SECURE=true
```

**Dokploy:** Compose servisi açılır, repo bağlanır, compose yolu olarak `docker-compose.dokploy.yml` seçilir ve
değişkenler Environment sekmesine yazılır. Domains sekmesinde `web` servisinin 80 numaralı portuna domain bağlanır.

**Kendi VPS'iniz (nginx arkasında):** `web` servisini yalnızca yerel bir porta açan küçük bir override dosyası
eklenir, örneğin `127.0.0.1:3210:80`. Sunucudaki nginx de domaini o porta yönlendirir. Güncellemek için:

```bash
git pull && docker compose -f docker-compose.dokploy.yml -f docker-compose.vps.yml up -d --build
```

Yeni tablo ve sütunlar API açılırken otomatik eklenir (`ADD COLUMN IF NOT EXISTS`); ayrı bir migration adımı yoktur.

## Geliştirme

Docker'sız API ve arayüz:

```bash
docker compose up -d db
pip install -r backend/requirements.txt
python -m uvicorn app.main:app --app-dir backend --port 8010
npm --prefix frontend install
npm --prefix frontend run dev        # http://localhost:5173, /api → 127.0.0.1:8010
```

**Testler.** Birim testleri için `cd backend && python -m pytest` yeterli. Uçtan uca API testleri ayrı bir veritabanı
ister, çünkü tabloları silip yeniden kurar:

```bash
NEEDLE_TEST_DATABASE_URL=postgresql+psycopg://needle:needle@127.0.0.1:5432/needle_test python -m pytest
```

GitHub Actions her PR'da entegrasyon dahil backend testlerini ve arayüz derlemesini çalıştırır.

**Sistem testleri.** [`backend/sistem_testleri`](backend/sistem_testleri) her parçayı (ayarlar, LLM, embedding,
retrieval, reranker, brief ve eşleştirme akışı, API) tek başına çalıştırıp ne yaptığını adım adım ekrana yazar.
Öğrenmek ve denetlemek için.

**Analiz.** [`backend/analiz`](backend/analiz) eşik ve kararlılık ölçümlerini içerir. Örneğin aynı brief'in birkaç
çalıştırmada aynı kararı verip vermediği ve kanıt benzerlik eşiğinin nereye konacağı burada ölçüldü.

### Proje yapısı

```
backend/
  app/
    api/          HTTP uç noktaları (ihtiyaç, eşleştirme, tanıştırma, çağrı, pilot, rapor, hesap)
    graphs/       LangGraph akışları: brief_graph (brief + takip soruları), match_graph (eşleştirme)
    retrieval/    pgvector araması, çoklu sorgu, RRF, filtre gevşetme
    rerank/       LLM puanlama ve doğrudan çözüm denetimi
    prompts/      LLM yönergeleri
    db/           modeller ve açılışta şema güncellemesi
  seed/           girişim havuzu, örnek ihtiyaçlar, yönetici hesabı
  tests/          pytest (birim + entegrasyon)
  sistem_testleri/, analiz/
frontend/src/
  pages/          sayfalar (genel bakış, ihtiyaçlar, pilot, çağrılar, kurumlar, rapor...)
  components/     ortak bileşenler
```

## Yol haritası

- [x] Brief üretimi ve takip soruları
- [x] Gerekçeli eşleştirme, doğrudan çözüm denetimi, negatif eşleşme ve kanıt kontrolü
- [x] Tanıştırma, e-posta taslağı ve açık çağrı
- [x] Pilot yönetimi: plan, hedefler, kilometre taşları, güncelleme akışı, kapanış
- [x] Girişim hesapları, iki yönlü öneriler ve program raporu
- [x] Demo modu (kayıtlı LLM cevapları)
- [ ] Kapalı döngü: pilot sonucunun sonraki eşleştirmelerin ağırlığına geri dönmesi
- [ ] İhtiyacı yazan birim ile ihtiyacı yaşayan saha birimini ayrıştırma
- [ ] E-posta doğrulaması ve bildirimler

## Katkı

Katkı rehberi için [CONTRIBUTING.md](CONTRIBUTING.md) dosyasına bakın.

## Lisans

[Apache License 2.0](LICENSE)
