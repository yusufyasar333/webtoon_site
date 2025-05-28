import os
import re
from django.core.management.base import BaseCommand
from django.conf import settings
from webtoons.models import (
    Webtoon, Chapter, ChapterImage, ImportedWebtoon, ImportedChapter
)
from django.db.models import Count
from django.db import transaction
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Veritabanı ve media dosyalarını senkronize eder, yarım kalan bölümleri temizler'

    def add_arguments(self, parser):
        parser.add_argument(
            '--webtoon-slug',
            help='Belirli bir webtoon\'u senkronize etmek için slug belirtin'
        )
        parser.add_argument(
            '--fix-empty-chapters',
            action='store_true',
            help='Resmi olmayan bölümleri temizler'
        )
        parser.add_argument(
            '--clean-missing-images',
            action='store_true',
            help='Fiziksel olarak mevcut olmayan resim kayıtlarını veritabanından temizler (bölümleri silmez)'
        )
        parser.add_argument(
            '--delete-orphaned-media',
            action='store_true',
            help='Veritabanında olmayan media dosyalarını siler'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Gerçekte silme yapmadan ne olacağını gösterir'
        )

    def handle(self, *args, **options):
        webtoon_slug = options.get('webtoon_slug')
        fix_empty_chapters = options.get('fix_empty_chapters', False)
        clean_missing_images = options.get('clean_missing_images', False)
        delete_orphaned_media = options.get('delete_orphaned_media', False)
        dry_run = options.get('dry_run', False)
        
        # Belirli bir webtoon için mi yoksa tüm webtoonlar için mi çalışacak?
        if webtoon_slug:
            webtoons = Webtoon.objects.filter(slug=webtoon_slug)
            if not webtoons.exists():
                self.stdout.write(self.style.ERROR(f"'{webtoon_slug}' slug'ına sahip webtoon bulunamadı."))
                return
        else:
            webtoons = Webtoon.objects.all()
        
        total_empty_chapters = 0
        total_fixed_chapters = 0
        total_cleaned_images = 0
        
        # Her webtoon için
        for webtoon in webtoons:
            self.stdout.write(self.style.SUCCESS(f"Webtoon işleniyor: {webtoon.title}"))
            
            # Resmi olmayan bölümleri bul
            empty_chapters = Chapter.objects.annotate(
                image_count=Count('images')
            ).filter(
                webtoon=webtoon,
                image_count=0
            )
            
            if empty_chapters.exists():
                total_empty_chapters += empty_chapters.count()
                self.stdout.write(
                    self.style.WARNING(f"{empty_chapters.count()} adet resmi olmayan bölüm bulundu.")
                )
                
                if fix_empty_chapters:
                    with transaction.atomic():
                        for chapter in empty_chapters:
                            # İçeri aktarılmış bölüm kayıtlarını sil
                            imported_chapters = ImportedChapter.objects.filter(chapter=chapter)
                            if imported_chapters.exists():
                                if not dry_run:
                                    imported_chapters.delete()
                                self.stdout.write(f"  - İçeri aktarılmış bölüm kaydı silindi: {chapter.title}")
                            
                            # Bölümü sil
                            if not dry_run:
                                chapter.delete()
                            total_fixed_chapters += 1
                            self.stdout.write(f"  - Bölüm silindi: {chapter.title}")
            
            # Fiziksel olarak mevcut olmayan resim kayıtlarını veritabanından temizle
            if clean_missing_images:
                cleaned_images = self.clean_missing_image_records(webtoon, dry_run)
                total_cleaned_images += cleaned_images
            
            # Media klasöründeki resimlerle veritabanını senkronize et
            if delete_orphaned_media:
                self.sync_media_with_database(webtoon, dry_run)
        
        # Özet bilgisi
        self.stdout.write(self.style.SUCCESS("İşlem tamamlandı!"))
        self.stdout.write(f"Toplam boş bölüm sayısı: {total_empty_chapters}")
        if fix_empty_chapters:
            self.stdout.write(f"Temizlenen bölüm sayısı: {total_fixed_chapters}")
        if clean_missing_images:
            self.stdout.write(f"Veritabanından temizlenen resim kaydı: {total_cleaned_images}")
        
        if dry_run:
            self.stdout.write(self.style.WARNING("Bu bir kuru çalıştırma idi, herhangi bir değişiklik yapılmadı."))
    
    def clean_missing_image_records(self, webtoon, dry_run=False):
        """Fiziksel olarak mevcut olmayan resim kayıtlarını veritabanından temizler"""
        cleaned_count = 0
        
        # Bu webtoon'a ait tüm resim kayıtlarını al
        chapter_images = ChapterImage.objects.filter(chapter__webtoon=webtoon)
        
        self.stdout.write(f"  - {chapter_images.count()} resim kaydı kontrol ediliyor...")
        
        for img in chapter_images:
            if img.image:
                # Django'nun verdiği göreli yolu alın
                rel_path = str(img.image)
                # Tam dosya yolunu oluşturun
                full_path = os.path.join(settings.MEDIA_ROOT, rel_path)
                
                # Dosya fiziksel olarak mevcut değilse
                if not os.path.exists(full_path):
                    self.stdout.write(self.style.WARNING(f"  - Eksik resim dosyası bulundu: {rel_path}"))
                    
                    if not dry_run:
                        # Resim kaydını veritabanından sil, ancak bölümü silme
                        img.delete()
                        cleaned_count += 1
                        self.stdout.write(f"    - Veritabanından silindi: {os.path.basename(rel_path)}")
                    else:
                        self.stdout.write(f"    - [Kuru çalıştırma] Veritabanından silinecek: {os.path.basename(rel_path)}")
        
        if cleaned_count == 0:
            self.stdout.write(self.style.SUCCESS("  - Eksik resim dosyası bulunamadı."))
        else:
            self.stdout.write(self.style.SUCCESS(f"  - {cleaned_count} adet eksik resim kaydı temizlendi."))
        
        return cleaned_count
            
    def sync_media_with_database(self, webtoon, dry_run=False):
        """Media klasöründeki resimlerle veritabanını senkronize eder"""
        # Chapters klasörü
        chapters_dir = os.path.join(settings.MEDIA_ROOT, 'webtoons', 'chapters')
        if not os.path.exists(chapters_dir):
            self.stdout.write(self.style.WARNING(f"Chapters klasörü bulunamadı: {chapters_dir}"))
            return
            
        # Bu webtoon'a ait veritabanındaki resim dosyaları
        db_images = ChapterImage.objects.filter(chapter__webtoon=webtoon)
        db_image_paths = set()
        
        for img in db_images:
            if img.image:
                # Django'nun verdiği göreli yolu alın
                rel_path = str(img.image)
                # Tam dosya yolunu oluşturun
                full_path = os.path.join(settings.MEDIA_ROOT, rel_path)
                db_image_paths.add(full_path)
        
        # Bu webtoon'a ait chapters klasöründeki dosyaları bulma
        pattern = re.compile(fr"{re.escape(webtoon.slug)}_ch\d+_img\d+\.\w+")
        orphaned_files = []
        
        for root, dirs, files in os.walk(chapters_dir):
            for filename in files:
                if pattern.match(filename):
                    full_path = os.path.join(root, filename)
                    
                    # Bu dosya veritabanında kayıtlı değilse, yetim dosya olarak işaretle
                    if full_path not in db_image_paths:
                        orphaned_files.append(full_path)
        
        # Yetim dosyaları raporla
        if orphaned_files:
            self.stdout.write(
                self.style.WARNING(f"{len(orphaned_files)} adet veritabanında olmayan media dosyası bulundu.")
            )
            
            for file_path in orphaned_files:
                if delete_orphaned_media and not dry_run:
                    try:
                        os.remove(file_path)
                        self.stdout.write(f"  - Silindi: {os.path.basename(file_path)}")
                    except Exception as e:
                        self.stdout.write(self.style.ERROR(f"  - Silinirken hata: {os.path.basename(file_path)} - {e}"))
                else:
                    self.stdout.write(f"  - Yetim dosya: {os.path.basename(file_path)}")
        else:
            self.stdout.write(self.style.SUCCESS("Veritabanında olmayan media dosyası bulunamadı.")) 