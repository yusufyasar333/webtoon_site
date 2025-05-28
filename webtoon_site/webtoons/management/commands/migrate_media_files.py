import os
import shutil
from django.core.management.base import BaseCommand
from django.conf import settings
from webtoons.models import Webtoon, Chapter, ChapterImage
from django.core.files.storage import default_storage
from django.core.files import File
from django.db import transaction
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Mevcut resim dosyalarını yeni dosya yapısına taşır'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Gerçekte taşıma yapmadan ne olacağını gösterir'
        )

    def handle(self, *args, **options):
        dry_run = options.get('dry_run', False)
        
        self.stdout.write(self.style.SUCCESS("Resim dosyalarını yeni yapıya taşıma işlemi başlatılıyor..."))
        
        # MEDIA_ROOT klasörünü al
        media_root = settings.MEDIA_ROOT
        
        # Klasörlerin var olduğundan emin ol
        os.makedirs(os.path.join(media_root, 'webtoons', 'content'), exist_ok=True)
        os.makedirs(os.path.join(media_root, 'webtoons', 'covers'), exist_ok=True)
        
        # Tüm webtoonları işle
        for webtoon in Webtoon.objects.all():
            self.stdout.write(f"Webtoon işleniyor: {webtoon.title}")
            
            # Webtoon kapak resmini taşı
            if webtoon.thumbnail:
                old_path = webtoon.thumbnail.path
                old_name = os.path.basename(old_path)
                
                # Yeni dosya adını ve yolunu belirle
                ext = os.path.splitext(old_name)[1]
                new_name = f"{webtoon.slug}{ext}"
                new_relative_path = f"webtoons/covers/{new_name}"
                new_full_path = os.path.join(media_root, new_relative_path)
                
                self.stdout.write(f"  - Kapak resmi taşınıyor: {old_name} -> {new_name}")
                
                if not dry_run:
                    try:
                        # Klasörün var olduğundan emin ol
                        os.makedirs(os.path.dirname(new_full_path), exist_ok=True)
                        
                        # Dosyayı kopyala
                        shutil.copy2(old_path, new_full_path)
                        
                        # Veritabanını güncelle
                        webtoon.thumbnail.name = new_relative_path
                        webtoon.save(update_fields=['thumbnail'])
                        
                        self.stdout.write(self.style.SUCCESS(f"    - Kapak resmi başarıyla taşındı."))
                    except Exception as e:
                        self.stdout.write(self.style.ERROR(f"    - Hata: {e}"))
            
            # Bölümleri işle
            for chapter in webtoon.chapters.all():
                self.stdout.write(f"  - Bölüm işleniyor: {chapter.title}")
                
                # Bölüm klasörünü oluştur
                chapter_number = str(chapter.number).replace('.', '-')
                chapter_folder = f"webtoons/content/{webtoon.slug}/chapter-{chapter_number}"
                chapter_full_path = os.path.join(media_root, chapter_folder)
                
                if not dry_run:
                    os.makedirs(chapter_full_path, exist_ok=True)
                
                # Bölüm resimlerini taşı
                for image in chapter.images.all():
                    if image.image:
                        old_path = image.image.path
                        old_name = os.path.basename(old_path)
                        
                        # Yeni dosya adını ve yolunu belirle
                        ext = os.path.splitext(old_name)[1]
                        new_name = f"{image.order:03d}{ext}"
                        new_relative_path = f"{chapter_folder}/{new_name}"
                        new_full_path = os.path.join(media_root, new_relative_path)
                        
                        self.stdout.write(f"    - Resim taşınıyor: {old_name} -> {new_name}")
                        
                        if not dry_run:
                            try:
                                # Dosyayı kopyala
                                shutil.copy2(old_path, new_full_path)
                                
                                # Veritabanını güncelle
                                image.image.name = new_relative_path
                                image.save(update_fields=['image'])
                                
                                self.stdout.write(self.style.SUCCESS(f"      - Resim başarıyla taşındı."))
                            except Exception as e:
                                self.stdout.write(self.style.ERROR(f"      - Hata: {e}"))
        
        # Özet bilgisi
        self.stdout.write(self.style.SUCCESS("İşlem tamamlandı!"))
        
        if dry_run:
            self.stdout.write(self.style.WARNING("Bu bir kuru çalıştırma idi, herhangi bir değişiklik yapılmadı.")) 