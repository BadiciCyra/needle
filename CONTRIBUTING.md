# Katkı Rehberi

Needle'a katkı vermek istediğin için teşekkürler!

## Başlarken

1. Repoyu fork'la ve klonla.
2. `main` dalından yeni bir dal aç: `git checkout -b feat/kisa-aciklama`
3. Değişikliğini yap, commit'le ve pull request aç.

## Dal isimleri

| Önek | Kullanım |
|---|---|
| `feat/` | Yeni özellik |
| `fix/` | Hata düzeltme |
| `docs/` | Dokümantasyon |
| `refactor/` | Davranışı değiştirmeyen kod düzenlemesi |
| `chore/` | Araç, bağımlılık, yapılandırma |

## Commit mesajları

[Conventional Commits](https://www.conventionalcommits.org/tr/) formatını kullanıyoruz:

```
feat(matching): negatif eşleşme gerekçesini kaydet
fix(brief): boş metinde takip sorusu üretme
docs: kurulum adımlarını ekle
```

## Pull request

- Her PR tek bir işe odaklansın.
- Ne değiştiğini ve neden değiştiğini kısaca açıkla.
- Arayüz değişikliklerinde ekran görüntüsü ekle.
- `main` dalına doğrudan push yapma.

## Kapsam

Proje bilinçli olarak dört adımla sınırlı: **girdi → brief → eşleştirme → pilot takibi**.
Bu kapsamın dışındaki özellik önerileri için önce bir issue açıp tartışalım.

## Hata bildirimi

Issue açarken şunları ekle:

- Ne yapmaya çalıştın?
- Ne bekliyordun, ne oldu?
- Hatayı yeniden üretme adımları
