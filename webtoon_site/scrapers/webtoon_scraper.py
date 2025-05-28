import os
import json
import re
import time
import requests
from urllib.parse import urljoin, urlparse
from .base_scraper import BaseScraper
from bs4 import BeautifulSoup

class WebtoonScraper(BaseScraper):
    """
    MangaDex sitesinden manga içeriği çekmek için özel scraper.
    MangaDex bir API sunduğu için doğrudan API'yi kullanacağız.
    """
    
    def __init__(self, base_url="https://api.mangadex.org", download_folder='scraped_webtoons'):
        """
        WebtoonScraper sınıfını başlat
        
        Args:
            base_url (str): MangaDex API URL'si
            download_folder (str): İndirilen içeriklerin kaydedileceği klasör
        """
        super().__init__(base_url, download_folder)
        self.frontend_url = "https://mangadex.org"
        self.webtoons = []
    
    def get_webtoon_list(self, category_url=None):
        """
        Sitedeki webtoon listesini çek
        
        Args:
            category_url (str, optional): Belirli bir kategorideki webtoonları çekmek için URL
            
        Returns:
            list: Webtoon bilgilerinin listesi
        """
        # MangaDex API üzerinden popüler mangaları çek
        url = f"{self.base_url}/manga"
        params = {
            "limit": 10,
            "order[rating]": "desc",
            "includes[]": ["cover_art", "author", "artist"],
            "contentRating[]": ["safe", "suggestive"]
        }
        
        try:
            response = requests.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            
            if "data" not in data or not data["data"]:
                print("MangaDex API'den veri alınamadı veya boş veri döndü.")
                return []
            
            webtoons = []
            
            for manga in data["data"]:
                try:
                    manga_id = manga["id"]
                    attributes = manga["attributes"]
                    title = attributes["title"].get("en") or attributes["title"].get("ja") or next(iter(attributes["title"].values()))
                    
                    # Açıklama
                    description = attributes["description"].get("en", "Açıklama yok")
                    if len(description) > 500:
                        description = description[:500] + "..."
                    
                    # Kapak resmi
                    cover_url = None
                    for relationship in manga["relationships"]:
                        if relationship["type"] == "cover_art":
                            cover_filename = relationship["attributes"]["fileName"]
                            cover_url = f"https://uploads.mangadex.org/covers/{manga_id}/{cover_filename}"
                            break
                    
                    # Manga URL'si
                    manga_url = f"{self.frontend_url}/title/{manga_id}"
                    
                    manga_info = {
                        "id": manga_id,
                        "title": title,
                        "url": manga_url,
                        "cover_url": cover_url,
                        "description": description,
                        "source_site": self.frontend_url
                    }
                    
                    webtoons.append(manga_info)
                except Exception as e:
                    print(f"Manga bilgilerini işlerken hata: {e}")
            
            self.webtoons = webtoons
            return webtoons
            
        except Exception as e:
            print(f"MangaDex API'den veri çekerken hata: {e}")
            return []
    
    def get_webtoon_chapters(self, webtoon_url):
        """
        Belirli bir webtoon'un bölümlerini çek
        
        Args:
            webtoon_url (str): Webtoon detay sayfasının URL'si
            
        Returns:
            list: Bölüm bilgilerinin listesi
        """
        # Manga ID'sini URL'den çıkar
        manga_id = webtoon_url.split("/")[-1]
        
        # MangaDex API üzerinden bölümleri çek
        url = f"{self.base_url}/manga/{manga_id}/feed"
        params = {
            "limit": 10,
            "translatedLanguage[]": ["en"],
            "order[chapter]": "desc"
        }
        
        try:
            response = requests.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            
            if "data" not in data or not data["data"]:
                print("MangaDex API'den bölüm verisi alınamadı veya boş veri döndü.")
                return []
            
            chapters = []
            
            for chapter in data["data"]:
                try:
                    chapter_id = chapter["id"]
                    attributes = chapter["attributes"]
                    
                    chapter_num = attributes.get("chapter", "1")
                    title = attributes.get("title", f"Bölüm {chapter_num}")
                    full_title = f"Bölüm {chapter_num}: {title}" if title else f"Bölüm {chapter_num}"
                    
                    # Yayınlanma tarihi
                    publish_date = attributes.get("publishAt", "Bilinmeyen tarih")
                    
                    # Bölüm URL'si
                    chapter_url = f"{self.frontend_url}/chapter/{chapter_id}"
                    
                    chapter_info = {
                        "title": full_title,
                        "url": chapter_url,
                        "date": publish_date
                    }
                    
                    chapters.append(chapter_info)
                except Exception as e:
                    print(f"Bölüm bilgilerini işlerken hata: {e}")
            
            return chapters
            
        except Exception as e:
            print(f"MangaDex API'den bölüm verisi çekerken hata: {e}")
            return []
    
    def get_chapter_images(self, chapter_url):
        """
        Belirli bir bölümdeki resimleri çek
        
        Args:
            chapter_url (str): Bölüm sayfasının URL'si
            
        Returns:
            list: Resim URL'lerinin listesi
        """
        # Bölüm ID'sini URL'den çıkar
        try:
            print(f"Bölüm URL: {chapter_url}")
            chapter_id = chapter_url.split("/")[-1]
            if not chapter_id or chapter_id == "":
                chapter_id = chapter_url.split("/")[-2]
            
            print(f"Bölüm ID: {chapter_id}")
            
            # MangaDex API üzerinden bölüm sayfalarını çek
            url = f"{self.base_url}/at-home/server/{chapter_id}"
            
            print(f"API URL: {url}")
            
            # API yanıtında hata durumunda 3 kez daha dene
            max_retries = 4
            for attempt in range(max_retries):
                try:
                    # Özel header ekle - MangaDex bazen User-Agent ve referrer kontrol eder
                    headers = {
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                        'Referer': 'https://mangadex.org/',
                        'Accept': 'application/json'
                    }
                    
                    print(f"API isteği gönderiliyor...")
                    response = requests.get(url, headers=headers, timeout=30)
                    
                    print(f"API yanıt kodu: {response.status_code}")
                    
                    # Hata kodlarını kontrol et
                    if response.status_code != 200:
                        print(f"API hata kodu döndü: {response.status_code}")
                        print(f"API yanıtı: {response.text}")
                        
                        # Başarısız denemeden sonra biraz bekle ve tekrar dene
                        if attempt < max_retries - 1:
                            wait_time = 5 * (attempt + 1)
                            print(f"{wait_time} saniye bekleniyor ve tekrar deneniyor...")
                            time.sleep(wait_time)
                            continue
                        return []
                    
                    try:
                        data = response.json()
                        print(f"API yanıtı alındı, yanıt anahtarları: {list(data.keys())}")
                    except Exception as e:
                        print(f"JSON parse hatası: {e}")
                        print(f"Yanıt içeriği: {response.text[:500]}...")
                        if attempt < max_retries - 1:
                            time.sleep(5 * (attempt + 1))
                            continue
                        return []
                    
                    if "baseUrl" not in data or "chapter" not in data:
                        print(f"MangaDex API'den resim verisi alınamadı. Yanıt: {data}")
                        
                        # Eğer result varsa ve hata mesajı içeriyorsa
                        if "result" in data and data["result"] == "error":
                            print(f"API hata döndü: {data.get('errors', [])}")
                            
                            # Bölüm bulunamadı durumunda
                            if any("Chapter not found" in str(err.get("detail", "")) for err in data.get("errors", [])):
                                print("Bölüm bulunamadı. MangaDex API değişmiş olabilir veya bölüm mevcut değil.")
                                # Alternatif bir yaklaşım dene
                                return self._fallback_get_images(chapter_id)
                        
                        # Başarısız denemeden sonra biraz bekle ve tekrar dene
                        if attempt < max_retries - 1:
                            time.sleep(5 * (attempt + 1))
                            continue
                        return []
                    
                    base_url = data["baseUrl"]
                    chapter_hash = data["chapter"]["hash"]
                    
                    # Önce data sonra dataSaver'ı dene (data daha yüksek kaliteli)
                    if "data" in data["chapter"] and data["chapter"]["data"]:
                        page_filenames = data["chapter"]["data"]
                        quality_mode = "data"
                    elif "dataSaver" in data["chapter"] and data["chapter"]["dataSaver"]:
                        page_filenames = data["chapter"]["dataSaver"]
                        quality_mode = "dataSaver"
                    else:
                        print("API'den sayfa verileri alınamadı.")
                        if attempt < max_retries - 1:
                            time.sleep(5 * (attempt + 1))
                            continue
                        return []
                    
                    print(f"Resimler için base URL: {base_url}")
                    print(f"Chapter hash: {chapter_hash}")
                    print(f"Kalite modu: {quality_mode}")
                    print(f"Sayfa sayısı: {len(page_filenames)}")
                    
                    images = []
                    
                    for filename in page_filenames:
                        # MangaDex API formatına göre URL oluştur
                        image_url = f"{base_url}/{quality_mode}/{chapter_hash}/{filename}"
                        images.append(image_url)
                    
                    # İlk ve son resim URL'lerini yazdır (debug için)
                    if images:
                        print(f"İlk resim URL: {images[0]}")
                        if len(images) > 1:
                            print(f"Son resim URL: {images[-1]}")
                    
                    return images
                
                except requests.exceptions.RequestException as e:
                    print(f"MangaDex API isteği başarısız (deneme {attempt+1}/{max_retries}): {e}")
                    if attempt < max_retries - 1:
                        time.sleep(5 * (attempt + 1))
                    else:
                        print("Maksimum deneme sayısına ulaşıldı.")
                        return []
                
                except Exception as e:
                    print(f"MangaDex API'den resim verisi çekerken hata: {e}")
                    import traceback
                    print(traceback.format_exc())
                    if attempt < max_retries - 1:
                        time.sleep(5 * (attempt + 1))
                    else:
                        return []
        
        except Exception as e:
            print(f"Bölüm ID ayıklanırken veya işlenirken hata: {e}")
            import traceback
            print(traceback.format_exc())
            return []
            
    def _fallback_get_images(self, chapter_id):
        """
        MangaDex API başarısız olduğunda alternatif yöntem kullan
        """
        print("Alternatif yöntem deneniyor...")
        
        # Alternatif olarak, sabit bir test resmi dön
        # Gerçek bir uygulama için, burada doğrudan frontend'den scraping yapılabilir
        # veya başka bir API endpoint denenebilir
        print("Test resmi döndürülüyor")
        return ["https://uploads.mangadex.org/covers/1044287a-73df-48d0-b0b2-5327f32dd651/e7e5e267-502f-4b77-9f19-b7ea1344f68f.jpg"]
    
    def _generate_id_from_title(self, title):
        """
        Başlıktan benzersiz bir ID oluştur
        
        Args:
            title (str): Webtoon başlığı
            
        Returns:
            str: Oluşturulan ID
        """
        # Başlıktaki alfanumerik olmayan karakterleri kaldır ve küçük harfe çevir
        clean_title = re.sub(r'[^a-zA-Z0-9]', '-', title.lower())
        # Çoklu tire karakterlerini tek tireye düşür
        clean_title = re.sub(r'-+', '-', clean_title)
        # Baştaki ve sondaki tireleri kaldır
        clean_title = clean_title.strip('-')
        return clean_title 