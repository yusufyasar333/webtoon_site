import requests
from bs4 import BeautifulSoup
import os
import time
import random
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

class BaseScraper:
    """
    Webtoon sitelerinden içerik çekmek için temel sınıf.
    """
    
    def __init__(self, base_url, download_folder='scraped_data'):
        """
        Scraper'ı başlat
        
        Args:
            base_url (str): Hedef sitenin ana URL'si
            download_folder (str): İndirilen içeriklerin kaydedileceği klasör
        """
        self.base_url = base_url
        self.download_folder = download_folder
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.101 Safari/537.36'
        ]
        self._create_directories()
        self.webdriver = None
    
    def _create_directories(self):
        """Gerekli dizinleri oluştur"""
        if not os.path.exists(self.download_folder):
            os.makedirs(self.download_folder)
    
    def _get_random_user_agent(self):
        """Rastgele bir user agent seç"""
        return random.choice(self.user_agents)
    
    def get_html(self, url, use_selenium=False):
        """
        Belirtilen URL'den HTML içeriğini çek
        
        Args:
            url (str): HTML içeriği çekilecek URL
            use_selenium (bool): Selenium kullanılsın mı
            
        Returns:
            BeautifulSoup: Çekilen HTML içeriği
        """
        if use_selenium:
            return self._get_html_with_selenium(url)
        else:
            return self._get_html_with_requests(url)
    
    def _get_html_with_requests(self, url):
        """Requests kütüphanesi kullanarak HTML içeriğini çek"""
        headers = {'User-Agent': self._get_random_user_agent()}
        response = requests.get(url, headers=headers)
        response.raise_for_status()  # Hata durumunda exception fırlat
        return BeautifulSoup(response.content, 'html.parser')
    
    def _get_html_with_selenium(self, url):
        """Selenium kullanarak HTML içeriğini çek"""
        if self.webdriver is None:
            service = Service(ChromeDriverManager().install())
            self.webdriver = webdriver.Chrome(service=service)
        
        self.webdriver.get(url)
        # Sayfanın yüklenmesini bekle
        time.sleep(2)
        
        html_content = self.webdriver.page_source
        return BeautifulSoup(html_content, 'html.parser')
    
    def download_image(self, url, filename):
        """
        Belirtilen URL'den resmi indir ve kaydet
        
        Args:
            url (str): Resim URL'si
            filename (str): Kaydedilecek dosya adı
        
        Returns:
            bool: İndirme başarılı mı
        """
        try:
            headers = {'User-Agent': self._get_random_user_agent()}
            response = requests.get(url, headers=headers, stream=True)
            response.raise_for_status()
            
            file_path = os.path.join(self.download_folder, filename)
            with open(file_path, 'wb') as out_file:
                for chunk in response.iter_content(chunk_size=1024):
                    if chunk:
                        out_file.write(chunk)
            return True
        except Exception as e:
            print(f"Resim indirme hatası: {e}")
            return False
    
    def close(self):
        """Kaynakları temizle"""
        if self.webdriver:
            self.webdriver.quit()
            self.webdriver = None 