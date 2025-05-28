import os
import json
import re
import time
import requests
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
from .base_scraper import BaseScraper
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import logging
from selenium.webdriver.chrome.options import Options

class MangaZureScraper(BaseScraper):
    """
    MangaZure.net sitesinden manga içeriği çekmek için özel scraper.
    """
    
    def __init__(self, base_url="https://mangazure.net", download_folder='scraped_webtoons'):
        """
        MangaZureScraper sınıfını başlat
        
        Args:
            base_url (str): MangaZure sitesinin URL'si
            download_folder (str): İndirilen içeriklerin kaydedileceği klasör
        """
        super().__init__(base_url, download_folder)
        self.webtoons = []
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Referer': 'https://mangazure.net/',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8'
        }
        # Selenium driver'ı başlat
        self.driver = None
        self.wait = None
        self.logger = logging.getLogger(__name__)
    
    def _init_selenium(self):
        """Selenium driver'ı başlat"""
        if self.driver is None:
            try:
                # Chrome options oluştur
                chrome_options = Options()
                chrome_options.add_argument("--headless")  # Headless mod
                chrome_options.add_argument("--disable-gpu")  # GPU hızlandırmayı devre dışı bırak
                chrome_options.add_argument("--window-size=1920,1080")  # Pencere boyutu
                chrome_options.add_argument("--disable-extensions")  # Eklentileri devre dışı bırak
                chrome_options.add_argument("--no-sandbox")  # Güvenli olmayan mod (bazı sistemlerde gerekli)
                chrome_options.add_argument("--disable-dev-shm-usage")  # /dev/shm kullanımını devre dışı bırak
                
                # User-Agent belirt
                chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")
                
                # Chrome driver'ı başlat
                service = Service(ChromeDriverManager().install())
                self.driver = webdriver.Chrome(service=service, options=chrome_options)
                self.wait = WebDriverWait(self.driver, 10)  # 10 saniye bekle
                self.logger.info("Selenium driver başarıyla başlatıldı (headless mod)")
            except Exception as e:
                self.logger.error(f"Selenium driver başlatılırken hata oluştu: {e}")
                import traceback
                self.logger.error(traceback.format_exc())
    
    def wait_for_page_load(self):
        """Sayfanın yüklenmesini bekle"""
        try:
            time.sleep(2)  # Temel bekleme
            # Sayfa yüklenene kadar bekle
            self.wait.until(lambda d: d.execute_script('return document.readyState') == 'complete')
        except Exception as e:
            self.logger.warning(f"Sayfa yükleme beklemesi sırasında hata oluştu: {e}")
            # Hata olsa bile devam et, en azından bekledik
            time.sleep(3)
    
    def get_webtoon_list(self, category_url=None):
        """
        MangaZure'daki webtoon listesini çek
        
        Args:
            category_url (str, optional): Belirli bir kategorideki webtoonları çekmek için URL
            
        Returns:
            list: Webtoon bilgilerinin listesi
        """
        url = category_url if category_url else f"{self.base_url}/manga/"
        print(f"Webtoon listesi çekiliyor: {url}")
        
        try:
            response = requests.get(url, headers=self.headers, timeout=30)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            
            webtoons = []
            
            # Ana sayfadaki veya kategori sayfasındaki manga kartlarını bul
            manga_items = soup.select('.page-item-detail')
            
            print(f"Toplam {len(manga_items)} manga bulundu.")
            
            for item in manga_items:
                try:
                    # Başlık ve URL
                    title_elem = item.select_one('.post-title h3 a')
                    if not title_elem:
                        continue
                    
                    title = title_elem.text.strip()
                    manga_url = title_elem['href']
                    
                    # Kapak resmi
                    img_elem = item.select_one('.item-thumb img')
                    cover_url = None
                    if img_elem:
                        # data-src, data-lazy-src veya src özelliklerini kontrol et
                        cover_url = img_elem.get('data-src') or img_elem.get('data-lazy-src') or img_elem.get('src')
                        # Eğer göreli bir URL ise, tam URL'ye dönüştür
                        if cover_url and not cover_url.startswith(('http://', 'https://')):
                            cover_url = urljoin(self.base_url, cover_url)
                    
                    # Manga ID - URL'den çıkar
                    manga_id = os.path.basename(manga_url.rstrip('/'))
                    
                    # Açıklama - detay sayfasından çekilecek
                    description = "Açıklama webtoon detay sayfasından yüklenecek."
                    
                    manga_info = {
                        'id': manga_id,
                        'title': title,
                        'url': manga_url,
                        'cover_url': cover_url,
                        'description': description,
                        'source_site': self.base_url
                    }
                    
                    webtoons.append(manga_info)
                    print(f"Manga bulundu: {title}, Kapak URL: {cover_url}")
                    
                except Exception as e:
                    print(f"Manga işlenirken hata: {e}")
            
            self.webtoons = webtoons
            return webtoons
            
        except Exception as e:
            print(f"Webtoon listesi çekilirken hata: {e}")
            import traceback
            print(traceback.format_exc())
            return []
    
    def get_webtoon_details(self, url):
        """Manga detay sayfasından bilgileri çeker"""
        try:
            # Selenium driver'ı başlat
            self._init_selenium()
            
            if not self.driver:
                self.logger.error("Selenium driver başlatılamadı")
                return None
                
            self.logger.info(f"Manga detay sayfası açılıyor: {url}")
            self.driver.get(url)
            self.wait_for_page_load()
            
            # Sayfa yüklendikten sonra işlemlere devam et
            self.logger.info("Sayfa yüklendi, başlık elementi aranıyor")
            self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".post-title")))
            
            title_element = self.driver.find_element(By.CSS_SELECTOR, ".post-title")
            title = title_element.text.strip()
            self.logger.info(f"Başlık: {title}")
            
            # Kapak resmi
            cover_element = None
            try:
                cover_element = self.driver.find_element(By.CSS_SELECTOR, ".summary_image img")
            except:
                try:
                    cover_element = self.driver.find_element(By.CSS_SELECTOR, ".tab-summary img")
                except:
                    try:
                        cover_element = self.driver.find_element(By.CSS_SELECTOR, ".site-content img")
                    except:
                        pass
            
            cover_url = ""
            if cover_element:
                # Farklı özellikleri kontrol et
                for attr in ['data-src', 'data-lazy-src', 'src']:
                    try:
                        if cover_element.get_attribute(attr):
                            cover_url = cover_element.get_attribute(attr)
                            # Göreceli URL'yi mutlak URL'ye dönüştür
                            if cover_url.startswith('/'):
                                base_url = self.driver.current_url.split('://')[0] + '://' + self.driver.current_url.split('://')[1].split('/')[0]
                                cover_url = base_url + cover_url
                            break
                    except:
                        continue
            
            # Açıklama
            description = ""
            try:
                # Daha geniş CSS selector kullan
                selectors = [
                    ".summary__content", 
                    ".description-summary",
                    ".manga-excerpt",
                    ".c-page__content",
                    ".entry-content",
                    ".manga-summary"
                ]
                
                for selector in selectors:
                    try:
                        desc_element = self.driver.find_element(By.CSS_SELECTOR, selector)
                        description = desc_element.text.strip()
                        if description:
                            self.logger.info(f"Açıklama bulundu ({selector}): {description[:50]}...")
                            break
                    except:
                        continue
                        
                if not description:
                    # Açıklama bulunamadıysa, tüm metni çek ve işle
                    self.logger.info("Açıklama bulunamadı, genel metin aranıyor")
                    page_text = self.driver.find_element(By.TAG_NAME, "body").text
                    # İçinde "Açıklama" veya "Description" geçen paragrafları ara
                    import re
                    desc_section = re.search(r'(Açıklama|Description|Synopsis)[\s:]*([^\n]+(\n[^\n]+){0,5})', page_text)
                    if desc_section:
                        description = desc_section.group(2).strip()
                        self.logger.info(f"Metin içinde açıklama bulundu: {description[:50]}...")
            except Exception as e:
                self.logger.error(f"Açıklama çekilirken hata oluştu: {e}")
                
            if not description:
                description = f"{title} hakkında detaylı açıklama bulunamadı."
                self.logger.warning("Açıklama bulunamadı, varsayılan açıklama kullanılıyor")
            
            # Kategorileri çek
            categories = []
            try:
                category_elements = self.driver.find_elements(By.CSS_SELECTOR, ".genres-content a, .tags-content a")
                for element in category_elements:
                    category_name = element.text.strip()
                    if category_name:
                        categories.append(category_name)
            except Exception as e:
                self.logger.warning(f"Kategoriler çekilirken hata oluştu: {e}")
            
            # Url ve ID
            current_url = self.driver.current_url
            manga_id = current_url.split('/')[-1]
            if not manga_id:
                manga_id = current_url.split('/')[-2]
            
            return {
                'title': title,
                'cover_url': cover_url,
                'description': description,
                'url': current_url,
                'id': manga_id,
                'categories': categories
            }
        except Exception as e:
            self.logger.error(f"Manga detayları çekilirken hata oluştu: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            return None
    
    def get_chapter_urls(self, webtoon_url):
        """Bölüm URL'lerini çek"""
        chapters = self.get_webtoon_chapters(webtoon_url)
        return [chapter['url'] for chapter in chapters] if chapters else []

    def get_webtoon_info(self, url):
        """Manga bilgilerini çeker"""
        details = self.get_webtoon_details(url)
        if not details:
            return None
        
        # Bölüm URL'lerini çek
        chapter_urls = self.get_chapter_urls(url)
        
        # Tüm bilgileri birleştir
        return {
            'title': details['title'],
            'url': details['url'],
            'cover_url': details['cover_url'],
            'description': details['description'],
            'chapter_urls': chapter_urls,
            'id': details['id'],
            'categories': details['categories']
        }
    
    def get_webtoon_chapters(self, webtoon_url):
        """
        Belirli bir webtoon'un bölümlerini çek
        
        Args:
            webtoon_url (str): Webtoon detay sayfasının URL'si
            
        Returns:
            list: Bölüm bilgilerinin listesi
        """
        self.logger.info(f"Bölümler çekiliyor: {webtoon_url}")
        
        try:
            # Önce normal HTTP isteği ile deneyelim
            response = requests.get(webtoon_url, headers=self.headers, timeout=30)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            
            chapters = []
            
            # Bölüm listesi
            chapter_items = soup.select('.wp-manga-chapter')
            
            self.logger.info(f"HTTP ile toplam {len(chapter_items)} bölüm bulundu.")
            
            # Eğer HTTP isteği ile bölümler bulunamadıysa Selenium deneyelim
            if not chapter_items:
                self.logger.info("HTTP isteği ile bölüm bulunamadı, Selenium deneniyor...")
                return self._get_chapters_with_selenium(webtoon_url)
            
            # En yeni bölümler en üstte listeleniyor, sıralama için ters çevirelim
            chapter_items.reverse()
            
            for i, item in enumerate(chapter_items):
                try:
                    # Bölüm başlığı ve URL
                    chapter_link = item.select_one('a')
                    if not chapter_link:
                        continue
                    
                    chapter_url = chapter_link['href']
                    chapter_title = chapter_link.text.strip()
                    
                    # Bölüm numarasını başlıktan çıkar (örn: "Bölüm 123" -> "123")
                    chapter_num_match = re.search(r'Bölüm\s+(\d+)', chapter_title)
                    if not chapter_num_match:
                        chapter_num_match = re.search(r'Chapter\s+(\d+)', chapter_title)
                    
                    chapter_num = chapter_num_match.group(1) if chapter_num_match else str(i+1)
                    
                    # Bölüm tam adı
                    full_title = f"Bölüm {chapter_num}"
                    
                    # Yayınlanma tarihi
                    date_elem = item.select_one('.chapter-release-date')
                    release_date = date_elem.text.strip() if date_elem else "Bilinmeyen tarih"
                    
                    chapter_info = {
                        'title': full_title,
                        'url': chapter_url,
                        'date': release_date,
                        'number': int(chapter_num)
                    }
                    
                    chapters.append(chapter_info)
                    
                except Exception as e:
                    self.logger.error(f"Bölüm işlenirken hata: {e}")
            
            self.logger.info(f"İşlenen bölüm sayısı: {len(chapters)}")
            return chapters
            
        except Exception as e:
            self.logger.error(f"Bölümler çekilirken hata: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            # Hata durumunda Selenium ile dene
            self.logger.info("Hata nedeniyle Selenium ile bölüm çekme deneniyor...")
            return self._get_chapters_with_selenium(webtoon_url)
    
    def _get_chapters_with_selenium(self, webtoon_url):
        """Selenium kullanarak bölümleri çek"""
        self.logger.info(f"Selenium ile bölümler çekiliyor: {webtoon_url}")
        chapters = []
        
        try:
            # Selenium driver'ı başlat
            self._init_selenium()
            
            if not self.driver:
                self.logger.error("Selenium driver başlatılamadı")
                return []
            
            # Sayfayı aç
            self.driver.get(webtoon_url)
            self.wait_for_page_load()
            
            # Tüm bölümleri göster butonuna tıkla (varsa)
            try:
                show_all_button = self.driver.find_element(By.CSS_SELECTOR, ".btn-view-more, .show-all")
                if show_all_button:
                    self.logger.info("Tüm bölümleri göster butonuna tıklanıyor...")
                    show_all_button.click()
                    time.sleep(2)  # Bölümlerin yüklenmesini bekle
            except:
                self.logger.info("Tüm bölümleri göster butonu bulunamadı veya gerekli değil")
            
            # Bölüm listesini bul
            try:
                # Farklı bölüm liste selektörleri
                chapter_selectors = [
                    '.wp-manga-chapter',
                    '.main.version-chap li',
                    '.chapter-link',
                    '.chapter_list li',
                    '.chapter-item'
                ]
                
                chapter_elements = []
                for selector in chapter_selectors:
                    chapter_elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    if chapter_elements:
                        self.logger.info(f"Bölüm listesi bulundu: {selector} ({len(chapter_elements)} bölüm)")
                        break
                
                # En yeni bölümler en üstte listeleniyor, sıralama için ters çevirelim
                chapter_elements.reverse()
                
                for i, elem in enumerate(chapter_elements):
                    try:
                        # Bölüm bağlantısı
                        link_elem = elem.find_element(By.TAG_NAME, 'a')
                        chapter_url = link_elem.get_attribute('href')
                        chapter_title = link_elem.text.strip()
                        
                        # Bölüm numarasını başlıktan çıkar
                        chapter_num_match = re.search(r'Bölüm\s+(\d+)|Chapter\s+(\d+)', chapter_title)
                        if chapter_num_match:
                            chapter_num = chapter_num_match.group(1) or chapter_num_match.group(2)
                        else:
                            chapter_num = str(i+1)
                            
                        # Bölüm tam adı
                        full_title = f"Bölüm {chapter_num}"
                        
                        # Yayınlanma tarihi
                        date_text = "Bilinmeyen tarih"
                        try:
                            date_elem = elem.find_element(By.CSS_SELECTOR, '.chapter-release-date, .date')
                            date_text = date_elem.text.strip()
                        except:
                            pass
                        
                        chapter_info = {
                            'title': full_title,
                            'url': chapter_url,
                            'date': date_text,
                            'number': int(chapter_num)
                        }
                        
                        chapters.append(chapter_info)
                        
                    except Exception as e:
                        self.logger.error(f"Selenium ile bölüm işlenirken hata: {e}")
                
                self.logger.info(f"Selenium ile toplam {len(chapters)} bölüm işlendi")
                
            except Exception as e:
                self.logger.error(f"Selenium ile bölüm listesi işlenirken hata: {e}")
                import traceback
                self.logger.error(traceback.format_exc())
            
            # Yine de bölüm bulunamadıysa sayfanın HTML'ini incele
            if not chapters:
                self.logger.info("Selenium ile bölüm bulunamadı, sayfa HTML'i manuel olarak inceleniyor...")
                page_source = self.driver.page_source
                soup = BeautifulSoup(page_source, 'html.parser')
                
                # Muhtemel bölüm bağlantılarını ara
                all_links = soup.select('a')
                for i, link in enumerate(all_links):
                    href = link.get('href', '')
                    text = link.text.strip()
                    
                    # Bölüm bağlantısı olabilecek desenleri kontrol et
                    if ('bolum' in href.lower() or 'chapter' in href.lower() or 
                        'bolum' in text.lower() or 'chapter' in text.lower()):
                        
                        # Bölüm numarasını çıkarmaya çalış
                        chapter_num_match = re.search(r'Bölüm\s+(\d+)|Chapter\s+(\d+)|[/-](\d+)(?:/|$)', 
                                                     href + ' ' + text)
                        if chapter_num_match:
                            chapter_num = chapter_num_match.group(1) or chapter_num_match.group(2) or chapter_num_match.group(3)
                        else:
                            continue  # Bölüm numarası bulunamadıysa geç
                            
                        # Bölüm tam adı
                        full_title = f"Bölüm {chapter_num}"
                        
                        chapter_info = {
                            'title': full_title,
                            'url': urljoin(webtoon_url, href),
                            'date': 'Bilinmeyen tarih',
                            'number': int(chapter_num)
                        }
                        
                        # Tekrar eden bölümleri önle
                        if not any(c['number'] == int(chapter_num) for c in chapters):
                            chapters.append(chapter_info)
                
                # Bölümleri numara sırasına göre sırala
                chapters.sort(key=lambda x: x['number'])
                self.logger.info(f"Manuel HTML incelemesi ile toplam {len(chapters)} bölüm bulundu")
            
            return chapters
            
        except Exception as e:
            self.logger.error(f"Selenium ile bölüm çekme hatası: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            return []
        
        finally:
            # İşlem bitince driver'ı kapat
            if hasattr(self, 'driver') and self.driver:
                try:
                    self.driver.quit()
                    self.driver = None
                except:
                    pass
    
    def get_chapter_images(self, chapter_url):
        """
        Belirli bir bölümdeki resimleri çek
        
        Args:
            chapter_url (str): Bölüm sayfasının URL'si
            
        Returns:
            list: Resim URL'lerinin listesi
        """
        self.logger.info(f"Bölüm resimleri çekiliyor: {chapter_url}")
        
        try:
            # Önce normal HTTP isteği ile deneyelim
            response = requests.get(chapter_url, headers=self.headers, timeout=30)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            
            images = []
            
            # Resim URL'lerini al
            img_containers = soup.select('.reading-content .page-break img')
            
            self.logger.info(f"HTTP ile toplam {len(img_containers)} resim bulundu.")
            
            for img in img_containers:
                try:
                    # Resim URL'si
                    img_url = img.get('data-src') or img.get('src')
                    if img_url:
                        images.append(img_url)
                except Exception as e:
                    self.logger.error(f"Resim işlenirken hata: {e}")
            
            if not images:
                # Alternatif resim bulma yöntemi (bazı siteler Javascript ile resimleri yüklüyor)
                script_elements = soup.select('script')
                for script in script_elements:
                    if script.string and 'chapter_preloaded_images' in script.string:
                        # JSON dizisini içeren JavaScript kodunu bul
                        match = re.search(r'chapter_preloaded_images\s*=\s*(\[.*?\])', script.string, re.DOTALL)
                        if match:
                            try:
                                img_list = json.loads(match.group(1))
                                images = img_list
                                self.logger.info(f"Script içinden {len(images)} resim bulundu.")
                                break
                            except:
                                pass
            
            # Hala resim bulunamadıysa Selenium deneyelim
            if not images:
                self.logger.info("HTTP isteği ile resim bulunamadı, Selenium deneniyor...")
                return self._get_images_with_selenium(chapter_url)
            
            self.logger.info(f"HTTP isteği ile toplam {len(images)} resim işlendi")
            return images
            
        except Exception as e:
            self.logger.error(f"Bölüm resimleri çekilirken hata: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            
            # Hata durumunda Selenium ile deneyelim
            self.logger.info("Hata nedeniyle Selenium ile resim çekme deneniyor...")
            return self._get_images_with_selenium(chapter_url)

    def _get_images_with_selenium(self, chapter_url):
        """Selenium kullanarak bölüm resimlerini çek"""
        self.logger.info(f"Selenium ile resimler çekiliyor: {chapter_url}")
        images = []
        
        try:
            # Selenium driver'ı başlat
            self._init_selenium()
            
            if not self.driver:
                self.logger.error("Selenium driver başlatılamadı")
                return []
            
            # Sayfayı aç
            try:
                self.driver.get(chapter_url)
                self.wait_for_page_load()
                
                # Tüm sayfa seçenekleri için birkaç saniye bekle
                time.sleep(3)
            except Exception as page_error:
                self.logger.error(f"Sayfa açılırken hata: {page_error}")
                # Alternatif URL denemesi
                try:
                    # URL'yi temizle ve tekrar dene
                    clean_url = chapter_url.split('?')[0]
                    if clean_url != chapter_url:
                        self.logger.info(f"Alternatif URL deneniyor: {clean_url}")
                        self.driver.get(clean_url)
                        self.wait_for_page_load()
                        time.sleep(3)
                except:
                    self.logger.error("Alternatif URL de açılamadı")
            
            # Farklı selektörler deneyerek resimleri bul
            selectors = [
                '.reading-content .page-break img',
                '.entry-content img',
                '.container-chapter-reader img',
                '.chapter-container img',
                '.chapter-content img',
                '.main-reading-area img',
                '.reader-area img'
            ]
            
            for selector in selectors:
                try:
                    img_elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    if img_elements:
                        self.logger.info(f"Resimler bulundu: {selector} ({len(img_elements)} resim)")
                        
                        for img in img_elements:
                            # Önce data-src, data-original, data-lazy-src gibi attribute'leri kontrol et
                            for attr in ['data-src', 'data-original', 'data-lazy-src', 'data-original-src', 'src']:
                                try:
                                    img_url = img.get_attribute(attr)
                                    if img_url and not img_url.startswith('data:'):
                                        images.append(img_url)
                                        break
                                except:
                                    continue
                        
                        if images:
                            self.logger.info(f"Selenium ile {len(images)} resim bulundu.")
                            break  # Bir selektör ile resimler bulunduysa diğerlerine geçme
                except Exception as selector_error:
                    self.logger.error(f"Selektör {selector} ile resim ararken hata: {selector_error}")
            
            # Resimler yine bulunamadıysa, tüm sayfadaki resimleri tara
            if not images:
                self.logger.info("Selektörler ile resim bulunamadı, tüm sayfadaki resimleri taranıyor...")
                try:
                    all_images = self.driver.find_elements(By.TAG_NAME, "img")
                    for img in all_images:
                        # Çok küçük resimleri atla (büyük olasılıkla ikon veya dekoratif öğelerdir)
                        try:
                            width = img.get_attribute("width")
                            height = img.get_attribute("height")
                            if width and height:
                                try:
                                    if int(width) < 100 or int(height) < 100:
                                        continue
                                except ValueError:
                                    # Sayısal olmayan değerler olabilir
                                    pass
                        except:
                            pass
                        
                        # Resim URL'sini bul
                        for attr in ['data-src', 'data-original', 'data-lazy-src', 'src']:
                            try:
                                img_url = img.get_attribute(attr)
                                if img_url and not img_url.startswith('data:'):
                                    images.append(img_url)
                                    break
                            except:
                                continue
                    
                    self.logger.info(f"Tüm sayfadan {len(images)} potansiyel resim bulundu.")
                except Exception as all_images_error:
                    self.logger.error(f"Tüm sayfadaki resimleri tararken hata: {all_images_error}")
            
            # Son bir çare olarak JavaScript ile sayfadan resim bilgilerini çıkarma
            if not images:
                self.logger.info("Son çare: JavaScript ile resim aranıyor...")
                try:
                    # Sayfadaki tüm resimleri JavaScript ile çek
                    js_images = self.driver.execute_script("""
                        try {
                            var images = [];
                            document.querySelectorAll('img').forEach(function(img) {
                                try {
                                    if ((img.width > 100 && img.height > 100) || (!img.width && !img.height)) {
                                        var src = img.getAttribute('data-src') || img.getAttribute('data-original') || img.getAttribute('src');
                                        if (src && !src.startsWith('data:')) {
                                            images.push(src);
                                        }
                                    }
                                } catch(err) {}
                            });
                            return images;
                        } catch(err) {
                            return [];
                        }
                    """)
                    
                    if js_images and len(js_images) > 0:
                        images = js_images
                        self.logger.info(f"JavaScript ile {len(images)} resim bulundu.")
                except Exception as js_error:
                    self.logger.error(f"JavaScript ile resim arama hatası: {js_error}")
            
            # Hala resim bulunamadıysa son bir çare daha
            if not images:
                self.logger.info("Son çare: DOM içinden tüm resimleri çıkarmayı dene")
                try:
                    # Sayfanın kaynak kodunu al
                    page_source = self.driver.page_source
                    
                    # Regex ile resimleri çıkar
                    import re
                    img_patterns = [
                        r'data-src=["\'](https?://[^"\']+\.(jpg|jpeg|png|gif|webp))["\']',
                        r'data-original=["\'](https?://[^"\']+\.(jpg|jpeg|png|gif|webp))["\']',
                        r'data-lazy-src=["\'](https?://[^"\']+\.(jpg|jpeg|png|gif|webp))["\']',
                        r'src=["\'](https?://[^"\']+\.(jpg|jpeg|png|gif|webp))["\']'
                    ]
                    
                    for pattern in img_patterns:
                        found_images = re.findall(pattern, page_source)
                        if found_images:
                            for img in found_images:
                                if isinstance(img, tuple):
                                    img_url = img[0]  # URL, uzantı çiftinden URL'yi al
                                else:
                                    img_url = img
                                images.append(img_url)
                    
                    self.logger.info(f"Regex ile {len(images)} resim bulundu.")
                except Exception as regex_error:
                    self.logger.error(f"Regex ile resim arama hatası: {regex_error}")
            
            # Göreceli URL'leri mutlak URL'lere dönüştür
            processed_images = []
            for img_url in images:
                try:
                    # URL'yi temizle ve doğrula
                    if not img_url:
                        continue
                        
                    # Göreceli URL'yi mutlak URL'ye dönüştür
                    if not img_url.startswith(('http://', 'https://')):
                        img_url = urljoin(chapter_url, img_url)
                    
                    processed_images.append(img_url)
                except Exception as url_error:
                    self.logger.error(f"URL işlenirken hata: {url_error}")
            
            # Tekrarlanan URL'leri kaldır
            images = list(dict.fromkeys(processed_images))
            
            self.logger.info(f"Selenium ile toplam {len(images)} benzersiz resim işlendi")
            return images
            
        except Exception as e:
            self.logger.error(f"Selenium ile resim çekme hatası: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            return []
        
        finally:
            # İşlem bitince driver'ı kapat
            if hasattr(self, 'driver') and self.driver:
                try:
                    self.driver.quit()
                    self.driver = None
                except:
                    pass 