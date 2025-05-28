from django.contrib import admin
from django.urls import path
from django.shortcuts import redirect
from django.contrib import messages
from django.template.response import TemplateResponse
from django.utils.html import format_html
from .models import (
    Category, Webtoon, Chapter, ChapterImage, Comment, Rating, Bookmark, ReadingHistory,
    ExternalSource, ImportedWebtoon, ImportedChapter, ImportLog
)
from .services import import_webtoon_from_source, sync_webtoon_chapters
from .forms import ImportWebtoonForm
from . import admin_views

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug']
    prepopulated_fields = {'slug': ('name',)}
    search_fields = ['name']

class ChapterImageInline(admin.TabularInline):
    model = ChapterImage
    extra = 0
    fields = ('image', 'order', 'image_preview')
    readonly_fields = ('image_preview',)
    
    def image_preview(self, obj):
        if obj.image:
            return format_html('<img src="{}" style="max-height: 80px;" />', obj.image.url)
        return "Resim yok"

class ChapterInline(admin.TabularInline):
    model = Chapter
    extra = 0
    fields = ('title', 'number', 'release_date', 'published')

@admin.register(Chapter)
class ChapterAdmin(admin.ModelAdmin):
    list_display = ['webtoon', 'title', 'number', 'release_date', 'published']
    list_filter = ['published', 'webtoon']
    search_fields = ['title', 'webtoon__title']
    inlines = [ChapterImageInline]

@admin.register(Webtoon)
class WebtoonAdmin(admin.ModelAdmin):
    list_display = ['title', 'status', 'published', 'views', 'thumbnail_preview']
    list_filter = ['status', 'published', 'categories']
    search_fields = ['title', 'author', 'artist']
    prepopulated_fields = {'slug': ('title',)}
    inlines = [ChapterInline]
    filter_horizontal = ('categories',)
    
    def thumbnail_preview(self, obj):
        if obj.thumbnail:
            return format_html('<img src="{}" style="max-height: 50px;" />', obj.thumbnail.url)
        return "Thumbnail yok"
    
    thumbnail_preview.short_description = "Kapak"
    
    def delete_model(self, request, obj):
        """Webtoon silindiğinde tüm bağlı dosyaları da sil"""
        # Tüm bölümleri ve resimlerini silmek için
        for chapter in obj.chapters.all():
            for image in chapter.images.all():
                if image.image and hasattr(image.image, 'path'):
                    try:
                        import os
                        if os.path.isfile(image.image.path):
                            os.remove(image.image.path)
                    except:
                        pass
        
        # Thumbnail'i sil
        if obj.thumbnail and hasattr(obj.thumbnail, 'path'):
            try:
                import os
                if os.path.isfile(obj.thumbnail.path):
                    os.remove(obj.thumbnail.path)
            except:
                pass
        
        super().delete_model(request, obj)

@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ['user', 'webtoon', 'chapter', 'created_date']
    list_filter = ['created_date', 'webtoon']
    search_fields = ['content', 'user__username', 'webtoon__title']

@admin.register(Rating)
class RatingAdmin(admin.ModelAdmin):
    list_display = ['user', 'webtoon', 'score']
    list_filter = ['score']
    search_fields = ['user__username', 'webtoon__title']

@admin.register(Bookmark)
class BookmarkAdmin(admin.ModelAdmin):
    list_display = ['user', 'webtoon', 'created_date']
    list_filter = ['created_date']
    search_fields = ['user__username', 'webtoon__title']

@admin.register(ReadingHistory)
class ReadingHistoryAdmin(admin.ModelAdmin):
    list_display = ['user', 'chapter', 'last_read']
    list_filter = ['last_read']
    search_fields = ['user__username', 'chapter__webtoon__title']

@admin.register(ExternalSource)
class ExternalSourceAdmin(admin.ModelAdmin):
    list_display = ('name', 'base_url', 'active', 'import_button')
    list_filter = ('active',)
    search_fields = ('name', 'base_url')
    
    def import_button(self, obj):
        return format_html(
            '<a class="button" href="{}?url={}">Webtoon İçeri Aktar</a>',
            '/admin/webtoons/importedwebtoon/import-webtoon/',
            obj.base_url
        )
    
    import_button.short_description = "İşlem"

class ImportedChapterInline(admin.TabularInline):
    model = ImportedChapter
    extra = 0
    fields = ('chapter', 'original_url', 'external_id')
    readonly_fields = ('chapter', 'original_url', 'external_id')

@admin.register(ImportedWebtoon)
class ImportedWebtoonAdmin(admin.ModelAdmin):
    list_display = ('webtoon', 'source', 'external_id', 'auto_sync', 'last_sync', 'sync_button')
    list_filter = ('source', 'auto_sync')
    search_fields = ('webtoon__title', 'external_id')
    inlines = [ImportedChapterInline]
    readonly_fields = ('last_sync',)
    
    def sync_button(self, obj):
        return format_html(
            '<a class="button" href="{}">Senkronize Et</a>',
            f'/yonetim/webtoons/sync/?webtoon_id={obj.id}'
        )
    
    sync_button.short_description = "İşlem"
    
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('<path:object_id>/sync/', self.admin_site.admin_view(self.sync_webtoon_view), name='webtoons_importedwebtoon_sync'),
            path('import-webtoon/', self.admin_site.admin_view(self.import_webtoon_view), name='webtoons_import_webtoon'),
        ]
        return custom_urls + urls
    
    def sync_webtoon_view(self, request, object_id):
        """Bir webtoon'un bölümlerini senkronize et"""
        imported_webtoon = self.get_object(request, object_id)
        if imported_webtoon:
            try:
                # Log mesajı
                messages.info(request, f"{imported_webtoon.webtoon.title} için senkronizasyon başlatılıyor...")
                
                # Senkronizasyon işlemini başlat
                import logging
                logger = logging.getLogger(__name__)
                logger.info(f"Webtoon senkronizasyonu başlatılıyor: {imported_webtoon.webtoon.title} (ID: {imported_webtoon.id})")
                
                # Senkronizasyon fonksiyonunu çağır
                result = sync_webtoon_chapters(imported_webtoon)
                
                # Sonuçları işle
                if result.get('success', False):
                    new_chapters = result.get('new_chapters', 0)
                    if new_chapters > 0:
                        messages.success(request, f"{new_chapters} yeni bölüm başarıyla senkronize edildi.")
                    else:
                        messages.info(request, "Yeni bölüm bulunamadı.")
                else:
                    messages.error(request, f"Senkronizasyon hatası: {result.get('message', 'Bilinmeyen hata')}")
                
                # Kapak resmini yenilemeyi dene
                try:
                    from .services import download_image_to_django
                    from django.utils.text import slugify
                    import os
                    
                    # Önce MangaZure scraper'ı içe aktar
                    from scrapers.mangazure_scraper import MangaZureScraper
                    
                    # URL'ye göre uygun scraper'ı seç
                    if "mangazure.net" in imported_webtoon.original_url.lower():
                        scraper = MangaZureScraper()
                        # Detayları çek
                        details = scraper.get_webtoon_details(imported_webtoon.original_url)
                        
                        if details and details.get('cover_url') and not imported_webtoon.webtoon.thumbnail:
                            logger.info(f"Kapak resmi yenileniyor: {details['cover_url']}")
                            
                            # Kapak resmini indir
                            webtoon_slug = imported_webtoon.webtoon.slug
                            thumbnail_name = f"{webtoon_slug}_cover{os.path.splitext(details['cover_url'])[1] or '.jpg'}"
                            thumbnail = download_image_to_django(details['cover_url'], thumbnail_name)
                            
                            if thumbnail:
                                # Webtoon'u güncelle
                                imported_webtoon.webtoon.thumbnail = thumbnail
                                imported_webtoon.webtoon.save()
                                messages.success(request, "Kapak resmi başarıyla güncellendi.")
                                logger.info("Kapak resmi başarıyla güncellendi.")
                except Exception as cover_error:
                    logger.error(f"Kapak resmi güncelleme hatası: {cover_error}")
                    # Bu hata bilgisini gösterme, çünkü asıl işlem senkronizasyondu
                
            except Exception as e:
                import traceback
                logger.error(f"Senkronizasyon genel hatası: {e}")
                logger.error(traceback.format_exc())
                messages.error(request, f"Senkronizasyon sırasında hata oluştu: {str(e)}")
        else:
            messages.error(request, "Belirtilen webtoon bulunamadı.")
        
        return redirect('admin:webtoons_importedwebtoon_change', object_id)
    
    def import_webtoon_view(self, request):
        if request.method == 'POST':
            form = ImportWebtoonForm(request.POST)
            if form.is_valid():
                source_url = form.cleaned_data['source_url']
                source_name = form.cleaned_data['source_name']
                max_chapters = form.cleaned_data['max_chapters']
                
                try:
                    result = import_webtoon_from_source(source_url, source_name, True, max_chapters)
                    if result.get('success', False):
                        messages.success(request, f"{result['webtoon'].title} başarıyla içeri aktarıldı. {result.get('imported_chapters', 0)} bölüm içeri aktarıldı.")
                        return redirect('admin:webtoons_webtoon_change', result['webtoon'].id)
                    else:
                        messages.error(request, f"İçeri aktarma başarısız: {result.get('message', 'Bilinmeyen hata')}")
                except Exception as e:
                    messages.error(request, f"İçeri aktarma hatası: {e}")
        else:
            form = ImportWebtoonForm()
        
        context = {
            'form': form,
            'title': 'Webtoon İçeri Aktar',
            'opts': self.model._meta,
        }
        return TemplateResponse(request, 'admin/import_webtoon.html', context)

@admin.register(ImportedChapter)
class ImportedChapterAdmin(admin.ModelAdmin):
    list_display = ['chapter', 'imported_webtoon', 'external_id']
    list_filter = ['imported_webtoon__source']
    search_fields = ['chapter__title', 'external_id', 'original_url']

@admin.register(ImportLog)
class ImportLogAdmin(admin.ModelAdmin):
    list_display = ('source', 'imported_webtoon_title', 'status', 'start_time', 'end_time', 'imported_chapters')
    list_filter = ('status', 'source')
    search_fields = ('imported_webtoon__webtoon__title', 'message')
    readonly_fields = ('source', 'imported_webtoon', 'status', 'start_time', 'end_time', 'imported_chapters', 'message')
    
    def imported_webtoon_title(self, obj):
        if obj.imported_webtoon:
            return obj.imported_webtoon.webtoon.title
        return "-"
    
    imported_webtoon_title.short_description = "Webtoon"

# Admin site başlığını ve index başlığını değiştir
admin.site.site_header = 'Webtoon Yönetim Paneli'
admin.site.site_title = 'Webtoon Yönetimi'
admin.site.index_title = 'Webtoon Yönetimine Hoş Geldiniz'

# Admin URL'lerini ekliyoruz - lambda ile sonsuz döngü oluşturmasını engellemek için get_urls metodunu override etmek yerine
# doğrudan urls.py dosyasında tanımlamanız önerilir. Örnek olması için urlpatterns'a ekleyebilirsiniz:
# 
# urlpatterns = [
#     path('admin/import-webtoon/', admin_views.import_webtoon, name='import_webtoon'),
#     path('admin/sync-webtoons/', admin_views.sync_webtoons, name='sync_webtoons'),
#     path('admin/', admin.site.urls),
# ]
