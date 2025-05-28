def get_webtoon_info(self, url):
        """Manga bilgilerini API'den çeker"""
        # URL'den manga ID'sini çıkar
        manga_id = url.split('/')[-1]
        if manga_id == "":
            manga_id = url.split('/')[-2]
        
        try:
            # MangaDex API'si üzerinden manga bilgilerini çek
            api_url = f"https://api.mangadex.org/manga/{manga_id}?includes[]=cover_art&includes[]=author&includes[]=artist&includes[]=tag"
            response = requests.get(api_url, headers=self.headers)
            response.raise_for_status()
            data = response.json()
            
            if data.get('result') != 'ok' or not data.get('data'):
                self.logger.error(f"API yanıtı başarısız: {data}")
                return None
            
            manga_data = data['data']
            attributes = manga_data['attributes']
            
            # Başlık
            title = attributes['title'].get('en') or next(iter(attributes['title'].values()))
            
            # Açıklama
            description = attributes['description'].get('en', '') or next(iter(attributes['description'].values()), '')
            
            # Kapak resmi
            cover_url = None
            for relationship in manga_data['relationships']:
                if relationship['type'] == 'cover_art':
                    cover_filename = relationship['attributes']['fileName']
                    cover_url = f"https://uploads.mangadex.org/covers/{manga_id}/{cover_filename}"
                    break
            
            # Kategorileri çek (tag'ler)
            categories = []
            for tag in attributes.get('tags', []):
                if 'attributes' in tag and 'name' in tag['attributes']:
                    tag_name = tag['attributes']['name'].get('en') or next(iter(tag['attributes']['name'].values()), '')
                    if tag_name:
                        categories.append(tag_name)
            
            # Bölümlerin listesini çek
            chapter_urls = self.get_chapter_urls(manga_id)
            
            return {
                'title': title,
                'description': description,
                'cover_url': cover_url,
                'url': url,
                'id': manga_id,
                'chapter_urls': chapter_urls,
                'categories': categories
            }
            
        except Exception as e:
            self.logger.error(f"Manga bilgileri çekilirken hata: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            return None 