import os
import sys
import requests
import logging
from scrapers.mangazure_scraper import MangaZureScraper

# PythonAnywhere'deki API endpoint ve token
API_URL = 'https://<senin-pythonanywhere-domainin>/api/import-chapter/'  # <-- Burayı kendi domaininle değiştir
API_TOKEN = 'supersecretapitoken123'  # settings.py'deki ile aynı olmalı

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("SendToAPI")

def main():
    # Örnek scraping işlemi (MangaZure)
    scraper = MangaZureScraper()
    webtoon_list = scraper.get_webtoon_list()
    if not webtoon_list:
        logger.error("Hiç webtoon bulunamadı!")
        return
    webtoon_url = webtoon_list[0]['url']
    logger.info(f"Seçilen webtoon: {webtoon_url}")
    webtoon_info = scraper.get_webtoon_info(webtoon_url)
    if not webtoon_info:
        logger.error("Webtoon detayları alınamadı!")
        return
    # En son bölümü seç
    if not webtoon_info['chapter_urls']:
        logger.error("Hiç bölüm bulunamadı!")
        return
    chapter_url = webtoon_info['chapter_urls'][0]
    logger.info(f"Seçilen bölüm: {chapter_url}")
    images = scraper.get_chapter_images(chapter_url)
    if not images:
        logger.error("Bölümde hiç resim bulunamadı!")
        return
    # API'ya gönderilecek veri
    payload = {
        "webtoon": {
            "title": webtoon_info['title'],
            "slug": webtoon_info['id'],
            "description": webtoon_info['description'],
            "categories": webtoon_info.get('categories', []),
            "thumbnail_url": webtoon_info.get('cover_url', ''),
        },
        "chapter": {
            "number": 1,
            "title": "Bölüm 1",
            "images": images[:10],  # İlk 10 resmi gönder
        }
    }
    logger.info(f"API'ya veri gönderiliyor: {API_URL}")
    response = requests.post(
        API_URL,
        json=payload,
        headers={"X-API-TOKEN": API_TOKEN}
    )
    logger.info(f"API yanıtı: {response.status_code} - {response.text}")

if __name__ == "__main__":
    main() 