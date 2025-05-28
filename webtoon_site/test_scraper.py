import os
import sys
import logging

# Logging ayarlarını yapılandır
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("scraper_test.log"),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger("ScraperTest")

# Scrapers modülünü import edebilmek için
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from scrapers.webtoon_scraper import WebtoonScraper
    logger.info("WebtoonScraper modülü başarıyla import edildi.")
except Exception as e:
    logger.error(f"WebtoonScraper import hatası: {e}")
    sys.exit(1)

def test_scraper(url=None):
    logger.info(f"MangaDex API üzerinden scraper test ediliyor...")
    try:
        # Scraper oluştur - MangaDex için base_url önemli değil
        scraper = WebtoonScraper()
        logger.info("Scraper başarıyla oluşturuldu.")
        
        # Webtoon listesini çek
        logger.info("Manga listesi çekiliyor...")
        webtoons = scraper.get_webtoon_list()
        
        if not webtoons:
            logger.error("Manga listesi boş!")
            return False
        
        logger.info(f"{len(webtoons)} manga bulundu.")
        for i, webtoon in enumerate(webtoons):
            logger.info(f"Manga {i+1}: {webtoon['title']}")
            logger.info(f"  URL: {webtoon['url']}")
            logger.info(f"  Kapak: {webtoon['cover_url']}")
            logger.info(f"  Açıklama: {webtoon['description'][:100]}...")
            
            # İlk webtoon'un bölümlerini test et
            if i == 0 and webtoon['url']:
                logger.info(f"Bölümler çekiliyor... URL: {webtoon['url']}")
                chapters = scraper.get_webtoon_chapters(webtoon['url'])
                
                if not chapters:
                    logger.error("Bölüm listesi boş!")
                    return False
                
                logger.info(f"{len(chapters)} bölüm bulundu.")
                for j, chapter in enumerate(chapters[:3]):  # İlk 3 bölümü göster
                    logger.info(f"  Bölüm {j+1}: {chapter['title']}")
                    logger.info(f"    URL: {chapter['url']}")
                    
                    # İlk bölümün resimlerini test et
                    if j == 0:
                        logger.info(f"Resimler çekiliyor... URL: {chapter['url']}")
                        images = scraper.get_chapter_images(chapter['url'])
                        
                        if not images:
                            logger.error("Resim listesi boş!")
                            return False
                        
                        logger.info(f"{len(images)} resim bulundu.")
                        for k, img_url in enumerate(images[:3]):  # İlk 3 resmi göster
                            logger.info(f"    Resim {k+1}: {img_url}")
                
                break  # Sadece ilk webtoon'u test et
        
        return True
    
    except Exception as e:
        logger.error(f"Test sırasında hata oluştu: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False
    finally:
        try:
            scraper.close()
            logger.info("Scraper kapatıldı.")
        except Exception:
            pass

if __name__ == "__main__":
    logger.info("\n==================================================")
    logger.info("MangaDex API Scraper testi başlıyor")
    logger.info("==================================================")
    
    if test_scraper():
        logger.info("Test BAŞARILI!")
    else:
        logger.error("Test BAŞARISIZ!") 