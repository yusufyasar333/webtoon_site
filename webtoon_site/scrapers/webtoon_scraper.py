import os
import json
import re
import time
from urllib.parse import urljoin, urlparse
from webtoon_site.scrapers.base_scraper import BaseScraper

class WebtoonScraper(BaseScraper):
    """
    Örnek bir webtoon sitesinden içerik çekmek için özel scraper.
    Bu örnekte, popüler bir webtoon platformunun yapısını taklit eden bir scraper yapısı kuruyoruz.
    """
    
    def __init__(self, base_url="https://example-webtoon-site.com", download_folder='scraped_webtoons'):
        """
        WebtoonScraper sınıfını başlat
        
        Args:
            base_url (str): Hedef webtoon sitesinin ana URL'si
            download_folder (str): İndirilen içeriklerin kaydedileceği klasör
        """
        super().__init__(base_url, download_folder)
        # Webtoon'ları saklamak için yapı
        self.webtoons = []
    
    def get_webtoon_list(self, category_url=None):
        """
        Sitedeki webtoon listesini çek
        
        Args:
            category_url (str, optional): Belirli bir kategorideki webtoonları çekmek için URL
            
        Returns:
            list: Webtoon bilgilerinin listesi
        """
        url = category_url or f"{self.base_url}/webtoons"
        soup = self.get_html(url)
        
        webtoons = []
        # Bu seçiciler, hedef sitenin HTML yapısına göre değiştirilmelidir
        webtoon_cards = soup.select('.webtoon-card')  # Örnek CSS seçici
        
        for card in webtoon_cards:
            try:
                title_elem = card.select_one('.webtoon-title')
                title = title_elem.text.strip() if title_elem else "İsimsiz Webtoon"
                
                link_elem = card.select_one('a.webtoon-link')
                link = urljoin(self.base_url, link_elem['href']) if link_elem else None
                
                cover_elem = card.select_one('img.webtoon-cover')
                cover_url = urljoin(self.base_url, cover_elem['src']) if cover_elem else None
                
                desc_elem = card.select_one('.webtoon-description')
                description = desc_elem.text.strip() if desc_elem else "Açıklama yok"
                
                # Benzersiz bir ID oluştur
                webtoon_id = self._generate_id_from_title(title)
                
                webtoon_info = {
                    'id': webtoon_id,
                    'title': title,
                    'url': link,
                    'cover_url': cover_url,
                    'description': description,
                    'source_site': self.base_url
                }
                
                webtoons.append(webtoon_info)
            except Exception as e:
                print(f"Webtoon bilgilerini çekerken hata: {e}")
                continue
        
        self.webtoons = webtoons
        return webtoons
    
    def get_webtoon_chapters(self, webtoon_url):
        """
        Belirli bir webtoon'un bölümlerini çek
        
        Args:
            webtoon_url (str): Webtoon detay sayfasının URL'si
            
        Returns:
            list: Bölüm bilgilerinin listesi
        """
        soup = self.get_html(webtoon_url)
        
        chapters = []
        # Bu seçiciler, hedef sitenin HTML yapısına göre değiştirilmelidir
        chapter_items = soup.select('.chapter-item')  # Örnek CSS seçici
        
        for item in chapter_items:
            try:
                title_elem = item.select_one('.chapter-title')
                title = title_elem.text.strip() if title_elem else f"Bölüm {len(chapters) + 1}"
                
                link_elem = item.select_one('a.chapter-link')
                link = urljoin(self.base_url, link_elem['href']) if link_elem else None
                
                date_elem = item.select_one('.chapter-date')
                date = date_elem.text.strip() if date_elem else "Bilinmeyen tarih"
                
                chapter_info = {
                    'title': title,
                    'url': link,
                    'date': date
                }
                
                chapters.append(chapter_info)
            except Exception as e:
                print(f"Bölüm bilgilerini çekerken hata: {e}")
                continue
        
        return chapters
    
    def get_chapter_images(self, chapter_url):
        """
        Belirli bir bölümdeki resimleri çek
        
        Args:
            chapter_url (str): Bölüm sayfasının URL'si
            
        Returns:
            list: Resim URL'lerinin listesi
        """
        # Dinamik içerik yüklenen sayfalar için Selenium kullan
        soup = self.get_html(chapter_url, use_selenium=True)
        
        images = []
        # Bu seçiciler, hedef sitenin HTML yapısına göre değiştirilmelidir
        image_containers = soup.select('.chapter-image-container img')  # Örnek CSS seçici
        
        for img in image_containers:
            try:
                if 'src' in img.attrs:
                    img_url = urljoin(self.base_url, img['src'])
                    images.append(img_url)
            except Exception as e:
                print(f"Resim URL'si çekerken hata: {e}")
                continue
        
        return images
    
    def download_webtoon(self, webtoon_info, max_chapters=None):
        """
        Webtoon'u ve bölümlerini indir
        
        Args:
            webtoon_info (dict): Webtoon bilgileri
            max_chapters (int, optional): İndirilecek maksimum bölüm sayısı
            
        Returns:
            dict: İndirme sonuçları
        """
        webtoon_id = webtoon_info['id']
        webtoon_folder = os.path.join(self.download_folder, webtoon_id)
        
        if not os.path.exists(webtoon_folder):
            os.makedirs(webtoon_folder)
        
        # Kapak resmini indir
        cover_filename = f"{webtoon_id}_cover.jpg"
        cover_path = os.path.join(webtoon_folder, cover_filename)
        
        if webtoon_info['cover_url'] and not os.path.exists(cover_path):
            self.download_image(webtoon_info['cover_url'], os.path.join(webtoon_id, cover_filename))
        
        # Metadata dosyasını kaydet
        metadata = {
            'id': webtoon_info['id'],
            'title': webtoon_info['title'],
            'description': webtoon_info['description'],
            'source_url': webtoon_info['url'],
            'source_site': webtoon_info['source_site'],
            'cover_filename': cover_filename,
            'scraped_date': time.strftime('%Y-%m-%d %H:%M:%S')
        }
        
        with open(os.path.join(webtoon_folder, 'metadata.json'), 'w', encoding='utf-8') as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)
        
        # Bölümleri çek
        chapters = self.get_webtoon_chapters(webtoon_info['url'])
        
        if max_chapters:
            chapters = chapters[:max_chapters]
        
        downloaded_chapters = []
        
        for i, chapter in enumerate(chapters):
            chapter_folder = os.path.join(webtoon_folder, f"chapter_{i+1:03d}")
            
            if not os.path.exists(chapter_folder):
                os.makedirs(chapter_folder)
            
            # Bölüm metadata
            chapter_metadata = {
                'title': chapter['title'],
                'source_url': chapter['url'],
                'date': chapter['date'],
                'number': i + 1
            }
            
            with open(os.path.join(chapter_folder, 'metadata.json'), 'w', encoding='utf-8') as f:
                json.dump(chapter_metadata, f, ensure_ascii=False, indent=2)
            
            # Bölüm resimlerini indir
            images = self.get_chapter_images(chapter['url'])
            downloaded_images = []
            
            for j, img_url in enumerate(images):
                img_filename = f"image_{j+1:03d}.jpg"
                img_path = os.path.join(chapter_folder, img_filename)
                
                if not os.path.exists(img_path):
                    success = self.download_image(img_url, os.path.join(webtoon_id, f"chapter_{i+1:03d}", img_filename))
                    if success:
                        downloaded_images.append(img_filename)
            
            chapter_metadata['images'] = downloaded_images
            
            # Güncellenen bölüm metadata
            with open(os.path.join(chapter_folder, 'metadata.json'), 'w', encoding='utf-8') as f:
                json.dump(chapter_metadata, f, ensure_ascii=False, indent=2)
            
            downloaded_chapters.append({
                'title': chapter['title'],
                'number': i + 1,
                'image_count': len(downloaded_images)
            })
        
        return {
            'webtoon': webtoon_info['title'],
            'chapters_downloaded': len(downloaded_chapters),
            'chapters': downloaded_chapters
        }
    
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
        # Birden fazla çizgiyi tek çizgiye indir
        clean_title = re.sub(r'-+', '-', clean_title)
        # Baştaki ve sondaki çizgileri kaldır
        clean_title = clean_title.strip('-')
        return clean_title 