# Webtoon Sitesi Projesi

Bu proje, Django kullanarak bir webtoon sitesi oluşturmayı ve diğer sitelerden içerik çekmeyi amaçlamaktadır.

## Kurulum

1. Python 3.8+ kurulu olmalıdır
2. Gerekli paketleri yükleyin:

```bash
pip install -r requirements.txt
```

3. Django migrasyonlarını çalıştırın:

```bash
cd webtoon_site
python manage.py migrate
```

4. Sunucuyu başlatın:

```bash
python manage.py runserver
```

## Scraping Modülü Kullanımı

```python
from webtoon_site.scrapers.webtoon_scraper import WebtoonScraper

# Scraper'ı başlat (örnek URL ile)
scraper = WebtoonScraper(base_url="https://example-webtoon-site.com")

# Webtoon listesini çek
webtoons = scraper.get_webtoon_list()

# İlk webtoon'u indir (en fazla 5 bölüm)
if webtoons:
    result = scraper.download_webtoon(webtoons[0], max_chapters=5)
    print(f"{result['webtoon']} - {result['chapters_downloaded']} bölüm indirildi.")

# Kaynakları temizle
scraper.close()
```

## Proje Yapısı

- `webtoon_site/` - Ana Django projesi
- `webtoon_site/scrapers/` - Web scraping modülleri
- `media/` - Yüklenen medya dosyaları
- `static/` - Statik dosyalar

## Katkıda Bulunma

1. Bu repository'yi fork edin
2. Feature branch'i oluşturun: `git checkout -b yeni-ozellik`
3. Değişikliklerinizi commit edin: `git commit -m 'Yeni özellik eklendi'`
4. Branch'inizi push edin: `git push origin yeni-ozellik`
5. Pull request gönderin 