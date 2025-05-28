from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.urls import reverse
from django.utils.text import slugify
from django.conf import settings
from django.db.models.signals import post_delete
from django.dispatch import receiver
import os

def webtoon_thumbnail_path(instance, filename):
    """Webtoon kapak resmi için dosya yolu belirler"""
    # Dosya uzantısını al
    ext = filename.split('.')[-1]
    # Yeni dosya adı oluştur
    filename = f"{instance.slug}.{ext}"
    # Dosya yolunu döndür
    return f'webtoons/covers/{filename}'

def chapter_image_path(instance, filename):
    """Bölüm resimleri için dosya yolu belirler"""
    # Webtoon ve bölüm bilgilerini al
    webtoon_slug = instance.chapter.webtoon.slug
    chapter_number = str(instance.chapter.number).replace('.', '-')
    
    # Dosya uzantısını al
    ext = filename.split('.')[-1]
    
    # Sıra numarasına göre dosya adı oluştur
    filename = f"{instance.order:03d}.{ext}"
    
    # Dosya yolunu döndür
    return f'webtoons/content/{webtoon_slug}/chapter-{chapter_number}/{filename}'

class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    
    class Meta:
        verbose_name_plural = 'Categories'
    
    def __str__(self):
        return self.name
    
    def get_absolute_url(self):
        return reverse('category_detail', args=[self.slug])

class Webtoon(models.Model):
    STATUS_CHOICES = (
        ('ongoing', 'Devam Ediyor'),
        ('completed', 'Tamamlandı'),
        ('hiatus', 'Ara Verildi'),
    )
    
    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200, unique=True)
    author = models.CharField(max_length=100)
    artist = models.CharField(max_length=100, blank=True)
    description = models.TextField()
    thumbnail = models.ImageField(upload_to=webtoon_thumbnail_path, blank=True, null=True)
    categories = models.ManyToManyField(Category, related_name='webtoons')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='ongoing')
    created_date = models.DateTimeField(auto_now_add=True)
    updated_date = models.DateTimeField(auto_now=True)
    published = models.BooleanField(default=True)
    views = models.PositiveIntegerField(default=0)
    
    class Meta:
        ordering = ['-created_date']
    
    def __str__(self):
        return self.title
    
    def get_absolute_url(self):
        return reverse('webtoon_detail', args=[self.slug])

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        super().save(*args, **kwargs)

class WebtoonsView(models.Model):
    webtoon = models.ForeignKey(Webtoon, on_delete=models.CASCADE, related_name='views_log')
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    viewed_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        constraints = [
            # Her kullanıcı her webtoon'u bir kez sayar
            models.UniqueConstraint(
                fields=['user', 'webtoon'],
                condition=models.Q(user__isnull=False),
                name='unique_user_webtoon'
            ),
            # Her IP her webtoon'u bir kez sayar
            models.UniqueConstraint(
                fields=['ip_address', 'webtoon'],
                condition=models.Q(ip_address__isnull=False),
                name='unique_ip_webtoon'
            ),
        ]
        
    def __str__(self):
        return f"{self.webtoon.title} viewed by {self.user or self.ip_address}"

class Chapter(models.Model):
    webtoon = models.ForeignKey(Webtoon, on_delete=models.CASCADE, related_name='chapters')
    title = models.CharField(max_length=200)
    number = models.PositiveIntegerField()
    release_date = models.DateTimeField(default=timezone.now)
    views = models.PositiveIntegerField(default=0)
    published = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['-number']
        unique_together = ['webtoon', 'number']
    
    def __str__(self):
        return f"{self.webtoon.title} - {self.title}"
    
    def get_absolute_url(self):
        return reverse('chapter_detail', args=[self.webtoon.slug, self.number])

class ChapterImage(models.Model):
    chapter = models.ForeignKey(Chapter, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to=chapter_image_path)
    order = models.PositiveIntegerField()
    
    def __str__(self):
        return f"{self.chapter} - Image {self.order}"
    
    class Meta:
        ordering = ['order']
        unique_together = ['chapter', 'order']

class Comment(models.Model):
    webtoon = models.ForeignKey(Webtoon, on_delete=models.CASCADE, related_name='comments')
    chapter = models.ForeignKey(Chapter, on_delete=models.CASCADE, related_name='comments', null=True, blank=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    content = models.TextField()
    created_date = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_date']
    
    def __str__(self):
        return f"{self.user.username} - {self.content[:50]}"

class Rating(models.Model):
    webtoon = models.ForeignKey(Webtoon, on_delete=models.CASCADE, related_name='ratings')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    score = models.PositiveSmallIntegerField()
    
    class Meta:
        unique_together = ['user', 'webtoon']
    
    def __str__(self):
        return f"{self.user.username} - {self.webtoon.title} - {self.score}"

class Bookmark(models.Model):
    webtoon = models.ForeignKey(Webtoon, on_delete=models.CASCADE, related_name='bookmarks')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='bookmarks')
    created_date = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['user', 'webtoon']
    
    def __str__(self):
        return f"{self.user.username} - {self.webtoon.title}"

class ReadingHistory(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reading_history')
    chapter = models.ForeignKey(Chapter, on_delete=models.CASCADE)
    last_read = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['user', 'chapter']
        ordering = ['-last_read']
    
    def __str__(self):
        return f"{self.user.username} - {self.chapter.webtoon.title} - Bölüm {self.chapter.number}"

# Dış kaynaklardan içeri aktarılan webtoonlar için modeller
class ExternalSource(models.Model):
    """Webtoon içeriklerinin çekildiği dış kaynakları temsil eder"""
    name = models.CharField(max_length=100)
    base_url = models.URLField()
    active = models.BooleanField(default=True)
    created_date = models.DateTimeField(auto_now_add=True)
    updated_date = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return self.name

class ImportedWebtoon(models.Model):
    """Dış kaynaklardan içeri aktarılan webtoonları temsil eder"""
    webtoon = models.OneToOneField(Webtoon, on_delete=models.CASCADE, related_name='import_info')
    source = models.ForeignKey(ExternalSource, on_delete=models.CASCADE, related_name='imported_webtoons')
    external_id = models.CharField(max_length=255, blank=True)
    original_url = models.URLField()
    last_sync = models.DateTimeField(auto_now=True)
    auto_sync = models.BooleanField(default=True)
    
    class Meta:
        unique_together = ['source', 'external_id']
    
    def __str__(self):
        return f"{self.webtoon.title} (from {self.source.name})"

class ImportedChapter(models.Model):
    """Dış kaynaklardan içeri aktarılan bölümleri temsil eder"""
    chapter = models.OneToOneField(Chapter, on_delete=models.CASCADE, related_name='import_info')
    imported_webtoon = models.ForeignKey(ImportedWebtoon, on_delete=models.CASCADE, related_name='imported_chapters')
    original_url = models.URLField()
    external_id = models.CharField(max_length=255, blank=True)
    
    def __str__(self):
        return f"{self.chapter.webtoon.title} - Bölüm {self.chapter.number} (from {self.imported_webtoon.source.name})"

class ImportLog(models.Model):
    """İçeri aktarma işlemlerinin loglarını tutar"""
    STATUS_CHOICES = (
        ('pending', 'Bekliyor'),
        ('running', 'Çalışıyor'),
        ('completed', 'Tamamlandı'),
        ('failed', 'Başarısız'),
    )
    
    source = models.ForeignKey(ExternalSource, on_delete=models.CASCADE, related_name='import_logs')
    imported_webtoon = models.ForeignKey(ImportedWebtoon, on_delete=models.CASCADE, related_name='import_logs', null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    start_time = models.DateTimeField(auto_now_add=True)
    end_time = models.DateTimeField(null=True, blank=True)
    message = models.TextField(blank=True)
    imported_chapters = models.PositiveIntegerField(default=0)
    
    class Meta:
        ordering = ['-start_time']
    
    def __str__(self):
        return f"{self.source.name} - {self.status} - {self.start_time.strftime('%Y-%m-%d %H:%M')}"

# Resim içeren modeller için silme sinyalleri
@receiver(post_delete, sender='webtoons.Webtoon')
def auto_delete_webtoon_file_on_delete(sender, instance, **kwargs):
    """
    Webtoon silindiğinde thumbnail dosyasını da sil
    """
    if instance.thumbnail:
        if os.path.isfile(instance.thumbnail.path):
            os.remove(instance.thumbnail.path)

@receiver(post_delete, sender='webtoons.ChapterImage')
def auto_delete_chapter_image_on_delete(sender, instance, **kwargs):
    """
    ChapterImage silindiğinde ilişkili dosyayı da sil
    """
    if instance.image:
        if os.path.isfile(instance.image.path):
            os.remove(instance.image.path)
