from django.contrib import admin
from .models import Category, Webtoon, Chapter, ChapterImage, Comment, Rating, Bookmark, ReadingHistory

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
