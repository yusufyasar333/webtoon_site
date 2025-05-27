"""
Webtoon scraper test script
"""
import os
import sys

# Projenin ana dizinini sys.path'e ekle
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from webtoon_site.scrapers.webtoon_scraper import WebtoonScraper

def test_scraper():
    """
    Örnek bir scraper testi çalıştır
    Not: Bu fonksiyon gerçek bir webtoon sitesini hedeflememeli, 
    sadece test amaçlı olarak tasarlanmış siteleri kullanmalıdır.
    """
    # Test amaçlı URL (gerçek bir site değil)
    test_url = "https://mangas.in"
    
    print(f"Scraper test başlatılıyor: {test_url}")
    
    try:
        # Scraper'ı başlat
        scraper = WebtoonScraper(base_url=test_url)
        
        # Webtoon listesini çekmeyi dene
        print("Webtoon listesi çekiliyor...")
        webtoons = scraper.get_webtoon_list()
        
        print(f"Toplam {len(webtoons)} webtoon bulundu.")
        
        # İlk birkaç webtoon'u göster
        for i, webtoon in enumerate(webtoons[:3]):
            print(f"Webtoon {i+1}: {webtoon['title']}")
            print(f"  - URL: {webtoon['url']}")
            print(f"  - Açıklama: {webtoon['description'][:50]}...")
        
        # Yalnızca ilk webtoon'un ilk bölümünü indir
        if webtoons:
            print(f"\nİlk webtoon'un ({webtoons[0]['title']}) ilk bölümünü indirme...")
            result = scraper.download_webtoon(webtoons[0], max_chapters=1)
            print(f"İndirme sonucu: {result['chapters_downloaded']} bölüm indirildi.")
        
    except Exception as e:
        print(f"Scraper test hatası: {e}")
    finally:
        # Scraper'ı kapat
        if 'scraper' in locals():
            scraper.close()
            print("Scraper kapatıldı.")
    
    print("Test tamamlandı.")

if __name__ == "__main__":
    test_scraper() 