"""
Scraper ile veritabanı entegrasyonunu sağlayan servis fonksiyonları
"""
import os
import tempfile
from datetime import datetime
from django.utils import timezone
from django.core.files import File
from django.db import transaction
from django.utils.text import slugify
import requests
from django.conf import settings
from webtoon_site.scrapers.webtoon_scraper import WebtoonScraper
from .models import (
    Webtoon, Chapter, ChapterImage, Category,
    ExternalSource, ImportedWebtoon, ImportedChapter, ImportLog
)

def download_image_to_django(image_url, file_name=None):
    """
    URL'den bir görsel indir ve Django dosya nesnesi olarak döndür
    
    Args:
        image_url (str): İndirilecek görselin URL'si
        file_name (str, optional): Dosya adı
        
    Returns:
        File: Django File nesnesi
    """
    if not file_name:
        file_name = os.path.basename(image_url)
    
    # Geçici dosya oluştur
    with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file_name)[1]) as temp_file:
        # Görseli indir
        response = requests.get(image_url, stream=True)
        response.raise_for_status()
        
        # Geçici dosyaya yaz
        for chunk in response.iter_content(chunk_size=8192):
            temp_file.write(chunk)
    
    # Django File nesnesi oluştur
    django_file = File(open(temp_file.name, 'rb'))
    django_file.name = file_name
    
    return django_file

def import_webtoon_from_source(source_url, source_name=None, auto_sync=True, max_chapters=None):
    """
    Bir kaynaktan webtoon içeriğini çek ve veritabanına kaydet
    
    Args:
        source_url (str): Kaynak URL
        source_name (str, optional): Kaynak adı
        auto_sync (bool): Otomatik senkronizasyon aktif mi?
        max_chapters (int, optional): Maksimum bölüm sayısı
        
    Returns:
        dict: İçeri aktarma sonuçları
    """
    # Scraper oluştur
    scraper = WebtoonScraper(base_url=source_url)
    
    try:
        # ExternalSource kaydı oluştur veya var olanı bul
        if not source_name:
            source_name = source_url.split('//')[1].split('/')[0]
        
        source, created = ExternalSource.objects.get_or_create(
            base_url=source_url,
            defaults={'name': source_name}
        )
        
        # Import log kaydı oluştur
        import_log = ImportLog.objects.create(
            source=source,
            status='running'
        )
        
        # Webtoon listesini çek
        webtoons = scraper.get_webtoon_list()
        
        if not webtoons:
            import_log.status = 'failed'
            import_log.message = 'Webtoon bulunamadı'
            import_log.end_time = timezone.now()
            import_log.save()
            return {'success': False, 'message': 'Webtoon bulunamadı'}
        
        # İlk webtoon'u al (örnek olarak)
        webtoon_info = webtoons[0]
        
        # İçeri aktarma işlemini transaction içinde yap
        with transaction.atomic():
            # Django Webtoon modeli oluştur
            webtoon_slug = slugify(webtoon_info['title'])
            
            # Eğer aynı slug ile webtoon varsa, slug'a benzersiz bir ek ekle
            if Webtoon.objects.filter(slug=webtoon_slug).exists():
                webtoon_slug = f"{webtoon_slug}-{source_name.lower()}"
                
                # Hala varsa, sonuna bir sayı ekle
                if Webtoon.objects.filter(slug=webtoon_slug).exists():
                    count = 1
                    while Webtoon.objects.filter(slug=f"{webtoon_slug}-{count}").exists():
                        count += 1
                    webtoon_slug = f"{webtoon_slug}-{count}"
            
            # Kapak resmini indir
            thumbnail = None
            if webtoon_info['cover_url']:
                try:
                    thumbnail_name = f"{webtoon_slug}_cover{os.path.splitext(webtoon_info['cover_url'])[1]}"
                    thumbnail = download_image_to_django(webtoon_info['cover_url'], thumbnail_name)
                except Exception as e:
                    import_log.message = f"Kapak resmi indirme hatası: {e}"
            
            # Webtoon kaydı oluştur
            webtoon = Webtoon.objects.create(
                title=webtoon_info['title'],
                slug=webtoon_slug,
                author='İçeri Aktarıldı',  # Kaynak siteden yazar bilgisi çekilebilir
                description=webtoon_info['description'],
                thumbnail=thumbnail,
                status='ongoing'  # Varsayılan değer
            )
            
            # Kategoriler ekle (örnek olarak)
            category, _ = Category.objects.get_or_create(
                name='İçeri Aktarılan',
                defaults={'slug': 'iceri-aktarilan'}
            )
            webtoon.categories.add(category)
            
            # ImportedWebtoon kaydı oluştur
            imported_webtoon = ImportedWebtoon.objects.create(
                webtoon=webtoon,
                source=source,
                external_id=webtoon_info.get('id', ''),
                original_url=webtoon_info['url'],
                auto_sync=auto_sync
            )
            
            # Import log güncelle
            import_log.imported_webtoon = imported_webtoon
            import_log.save()
            
            # Bölümleri çek
            chapters = scraper.get_webtoon_chapters(webtoon_info['url'])
            
            if max_chapters:
                chapters = chapters[:max_chapters]
            
            # Bölümleri içeri aktar
            imported_chapter_count = 0
            
            for i, chapter_info in enumerate(chapters):
                try:
                    # Bölüm kaydı oluştur
                    chapter = Chapter.objects.create(
                        webtoon=webtoon,
                        title=chapter_info['title'],
                        number=i + 1,  # Sıralı numara ver
                        release_date=timezone.now(),
                        published=True
                    )
                    
                    # ImportedChapter kaydı oluştur
                    imported_chapter = ImportedChapter.objects.create(
                        chapter=chapter,
                        imported_webtoon=imported_webtoon,
                        original_url=chapter_info['url'],
                        external_id=str(i + 1)  # Örnek olarak
                    )
                    
                    # Bölüm resimlerini çek
                    images = scraper.get_chapter_images(chapter_info['url'])
                    
                    # Bölüm resimlerini kaydet
                    for j, img_url in enumerate(images):
                        try:
                            img_ext = os.path.splitext(img_url)[1] or '.jpg'
                            img_name = f"{webtoon_slug}_ch{i+1:03d}_img{j+1:03d}{img_ext}"
                            image_file = download_image_to_django(img_url, img_name)
                            
                            # ChapterImage kaydı oluştur
                            ChapterImage.objects.create(
                                chapter=chapter,
                                image=image_file,
                                order=j
                            )
                        except Exception as e:
                            print(f"Resim indirme hatası: {e}")
                    
                    imported_chapter_count += 1
                    
                except Exception as e:
                    print(f"Bölüm içeri aktarma hatası: {e}")
            
            # Import log güncelle
            import_log.status = 'completed'
            import_log.end_time = timezone.now()
            import_log.imported_chapters = imported_chapter_count
            import_log.message = f"{webtoon.title} webtoon'u ve {imported_chapter_count} bölüm başarıyla içeri aktarıldı."
            import_log.save()
            
            return {
                'success': True,
                'webtoon': webtoon,
                'imported_webtoon': imported_webtoon,
                'imported_chapters': imported_chapter_count,
                'message': import_log.message
            }
    
    except Exception as e:
        # Hata durumunda log güncelle
        if 'import_log' in locals():
            import_log.status = 'failed'
            import_log.end_time = timezone.now()
            import_log.message = f"İçeri aktarma hatası: {e}"
            import_log.save()
        
        return {'success': False, 'message': f"İçeri aktarma hatası: {e}"}
    
    finally:
        # Scraper'ı kapat
        scraper.close()

def sync_webtoon_chapters(imported_webtoon, max_new_chapters=None):
    """
    Daha önce içeri aktarılmış bir webtoon'un yeni bölümlerini senkronize et
    
    Args:
        imported_webtoon (ImportedWebtoon): İçeri aktarılmış webtoon
        max_new_chapters (int, optional): Maksimum yeni bölüm sayısı
        
    Returns:
        dict: Senkronizasyon sonuçları
    """
    # Scraper oluştur
    scraper = WebtoonScraper(base_url=imported_webtoon.source.base_url)
    
    try:
        # Import log kaydı oluştur
        import_log = ImportLog.objects.create(
            source=imported_webtoon.source,
            imported_webtoon=imported_webtoon,
            status='running'
        )
        
        # Bölümleri çek
        chapters = scraper.get_webtoon_chapters(imported_webtoon.original_url)
        
        # Mevcut bölümleri bul
        existing_chapters = ImportedChapter.objects.filter(
            imported_webtoon=imported_webtoon
        ).values_list('original_url', flat=True)
        
        # Yeni bölümleri filtrele
        new_chapters = [ch for ch in chapters if ch['url'] not in existing_chapters]
        
        if max_new_chapters:
            new_chapters = new_chapters[:max_new_chapters]
        
        if not new_chapters:
            import_log.status = 'completed'
            import_log.end_time = timezone.now()
            import_log.message = 'Yeni bölüm bulunamadı'
            import_log.save()
            return {'success': True, 'new_chapters': 0, 'message': 'Yeni bölüm bulunamadı'}
        
        # İçeri aktarma işlemini transaction içinde yap
        with transaction.atomic():
            webtoon = imported_webtoon.webtoon
            last_chapter_number = Chapter.objects.filter(webtoon=webtoon).order_by('-number').first()
            start_number = last_chapter_number.number + 1 if last_chapter_number else 1
            
            # Yeni bölümleri içeri aktar
            imported_chapter_count = 0
            
            for i, chapter_info in enumerate(new_chapters):
                try:
                    # Bölüm kaydı oluştur
                    chapter = Chapter.objects.create(
                        webtoon=webtoon,
                        title=chapter_info['title'],
                        number=start_number + i,  # Sıralı numara ver
                        release_date=timezone.now(),
                        published=True
                    )
                    
                    # ImportedChapter kaydı oluştur
                    imported_chapter = ImportedChapter.objects.create(
                        chapter=chapter,
                        imported_webtoon=imported_webtoon,
                        original_url=chapter_info['url'],
                        external_id=str(start_number + i)  # Örnek olarak
                    )
                    
                    # Bölüm resimlerini çek
                    images = scraper.get_chapter_images(chapter_info['url'])
                    
                    # Bölüm resimlerini kaydet
                    for j, img_url in enumerate(images):
                        try:
                            img_ext = os.path.splitext(img_url)[1] or '.jpg'
                            img_name = f"{webtoon.slug}_ch{start_number+i:03d}_img{j+1:03d}{img_ext}"
                            image_file = download_image_to_django(img_url, img_name)
                            
                            # ChapterImage kaydı oluştur
                            ChapterImage.objects.create(
                                chapter=chapter,
                                image=image_file,
                                order=j
                            )
                        except Exception as e:
                            print(f"Resim indirme hatası: {e}")
                    
                    imported_chapter_count += 1
                    
                except Exception as e:
                    print(f"Bölüm içeri aktarma hatası: {e}")
            
            # Import log güncelle
            import_log.status = 'completed'
            import_log.end_time = timezone.now()
            import_log.imported_chapters = imported_chapter_count
            import_log.message = f"{webtoon.title} webtoon'u için {imported_chapter_count} yeni bölüm içeri aktarıldı."
            import_log.save()
            
            # Imported webtoon son senkronizasyon zamanını güncelle
            imported_webtoon.last_sync = timezone.now()
            imported_webtoon.save()
            
            return {
                'success': True,
                'webtoon': webtoon,
                'new_chapters': imported_chapter_count,
                'message': import_log.message
            }
    
    except Exception as e:
        # Hata durumunda log güncelle
        if 'import_log' in locals():
            import_log.status = 'failed'
            import_log.end_time = timezone.now()
            import_log.message = f"Senkronizasyon hatası: {e}"
            import_log.save()
        
        return {'success': False, 'message': f"Senkronizasyon hatası: {e}"}
    
    finally:
        # Scraper'ı kapat
        scraper.close() 