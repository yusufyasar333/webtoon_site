from django.contrib import admin
from django.urls import path
from django.utils.html import format_html
from django.urls import reverse
from .models import (
    Category, Webtoon, Chapter, ChapterImage, Comment, Rating, Bookmark, ReadingHistory,
    ExternalSource, ImportedWebtoon, ImportedChapter, ImportLog
)
from . import admin_views

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug']
    prepopulated_fields = {'slug': ('name',)}
    search_fields = ['name']

class ChapterImageInline(admin.TabularInline):
    model = ChapterImage
    extra = 1

@admin.register(Chapter)
class ChapterAdmin(admin.ModelAdmin):
    list_display = ['title', 'webtoon', 'number', 'release_date', 'published']
    list_filter = ['published', 'release_date', 'webtoon']
    search_fields = ['title', 'webtoon__title']
    inlines = [ChapterImageInline]

@admin.register(Webtoon)
class WebtoonAdmin(admin.ModelAdmin):
    list_display = ['title', 'author', 'status', 'published', 'created_date', 'views']
    list_filter = ['status', 'published', 'created_date', 'categories']
    search_fields = ['title', 'author', 'description']
    prepopulated_fields = {'slug': ('title',)}
    filter_horizontal = ['categories']

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
    list_display = ['name', 'base_url', 'active', 'created_date', 'updated_date']
    list_filter = ['active', 'created_date']
    search_fields = ['name', 'base_url']

class ImportedChapterInline(admin.TabularInline):
    model = ImportedChapter
    extra = 0
    fields = ['chapter', 'original_url', 'external_id']
    readonly_fields = ['chapter']

@admin.register(ImportedWebtoon)
class ImportedWebtoonAdmin(admin.ModelAdmin):
    list_display = ['webtoon', 'source', 'last_sync', 'auto_sync']
    list_filter = ['source', 'auto_sync', 'last_sync']
    search_fields = ['webtoon__title', 'external_id', 'original_url']
    inlines = [ImportedChapterInline]

@admin.register(ImportedChapter)
class ImportedChapterAdmin(admin.ModelAdmin):
    list_display = ['chapter', 'imported_webtoon', 'external_id']
    list_filter = ['imported_webtoon__source']
    search_fields = ['chapter__title', 'external_id', 'original_url']

@admin.register(ImportLog)
class ImportLogAdmin(admin.ModelAdmin):
    list_display = ['source', 'imported_webtoon', 'status', 'start_time', 'end_time', 'imported_chapters']
    list_filter = ['source', 'status', 'start_time']
    search_fields = ['message', 'imported_webtoon__webtoon__title']
    readonly_fields = ['source', 'imported_webtoon', 'status', 'start_time', 'end_time', 'message', 'imported_chapters']

# Admin site başlığını ve index başlığını değiştir
admin.site.site_header = 'Webtoon Yönetim Paneli'
admin.site.site_title = 'Webtoon Yönetimi'
admin.site.index_title = 'Webtoon Yönetimine Hoş Geldiniz'

# Admin site URL'lerini ekle
admin.site.get_urls = lambda: admin.site.urls[0] + [
    path('import-webtoon/', admin_views.import_webtoon, name='import_webtoon'),
    path('sync-webtoons/', admin_views.sync_webtoons, name='sync_webtoons'),
]
