from django.urls import path
from . import views
from . import admin_views

app_name = 'webtoons'

urlpatterns = [
    # Ana sayfalar
    path('', views.home, name='home'),
    path('browse/', views.browse, name='browse'),
    path('latest/', views.latest, name='latest'),
    path('popular/', views.popular, name='popular'),
    
    # Kategori sayfaları
    path('category/<slug:slug>/', views.category_detail, name='category_detail'),
    path('categories/', views.category_list, name='category_list'),
    
    # Webtoon sayfaları
    path('webtoon/<slug:slug>/', views.webtoon_detail, name='webtoon_detail'),
    path('webtoon/<slug:slug>/chapter/<str:number>/', views.chapter_detail, name='chapter_detail'),
    
    # Kullanıcı işlemleri
    path('accounts/profile/', views.user_profile, name='user_profile'),
    path('accounts/bookmarks/', views.user_bookmarks, name='user_bookmarks'),
    path('accounts/history/', views.user_history, name='user_history'),
    
    # API işlemleri
    path('api/bookmark/<int:webtoon_id>/', views.toggle_bookmark, name='toggle_bookmark'),
    path('api/rate/<int:webtoon_id>/', views.rate_webtoon, name='rate_webtoon'),
    path('api/comment/add/', views.add_comment, name='add_comment'),
    
    # Arama
    path('search/', views.search, name='search'),
    
    # Admin işlemleri
    path('yonetim/', views.admin_dashboard, name='admin_dashboard'),
    path('yonetim/webtoons/', views.admin_webtoon_list, name='admin_webtoon_list'),
    path('yonetim/webtoons/create/', views.admin_webtoon_create, name='admin_webtoon_create'),
    
    # Webtoon İçeri Aktarma ve Senkronizasyon İşlemleri
    path('yonetim/webtoons/import/', views.admin_import_webtoon, name='admin_import_webtoon'),
    path('yonetim/webtoons/sync/', views.admin_sync_webtoons, name='admin_sync_webtoons'),
    path('yonetim/webtoons/fix-chapters/', views.admin_fix_chapters, name='admin_fix_chapters'),
    path('yonetim/webtoons/sync/<int:webtoon_id>/ajax/', views.admin_sync_webtoon_ajax, name='admin_sync_webtoon_ajax'),
    path('yonetim/webtoons/sync-all/ajax/', views.admin_sync_all_webtoons_ajax, name='admin_sync_all_webtoons_ajax'),
    
    # AFTER the more specific paths, place the ones with slug parameters
    path('yonetim/webtoons/<slug:slug>/', views.admin_webtoon_detail, name='admin_webtoon_detail'),
    path('yonetim/webtoons/<slug:slug>/edit/', views.admin_webtoon_edit, name='admin_webtoon_edit'),
    path('yonetim/webtoons/<slug:slug>/delete/', views.admin_webtoon_delete, name='admin_webtoon_delete'),
    path('yonetim/webtoons/<slug:slug>/chapter/create/', views.admin_chapter_create, name='admin_chapter_create'),
    path('yonetim/webtoons/<slug:slug>/chapter/<str:number>/edit/', views.admin_chapter_edit, name='admin_chapter_edit'),
    path('yonetim/webtoons/<slug:slug>/chapter/<str:number>/delete/', views.admin_chapter_delete, name='admin_chapter_delete'),
    
    # Kategori yönetimi
    path('yonetim/kategoriler/', views.admin_category_list, name='admin_category_list'),
    path('yonetim/kategoriler/<slug:slug>/edit/', views.admin_category_edit, name='admin_category_edit'),
    path('yonetim/kategoriler/<slug:slug>/delete/', views.admin_category_delete, name='admin_category_delete'),
    path('import/', views.import_webtoon, name='import_webtoon'),
    path('check-source/', views.check_source, name='check_source'),
]

# Eski Admin özel URL'leri (artık kullanılmıyor)
# urlpatterns += [
#     path('admin/webtoons/import-webtoon/', admin_views.import_webtoon, name='import_webtoon'),
#     path('admin/webtoons/sync-webtoons/', admin_views.sync_webtoons, name='sync_webtoons'),
#     path('admin/webtoons/sync-webtoon/<int:webtoon_id>/', admin_views.sync_webtoon_ajax, name='sync_webtoon_ajax'),
#     path('admin/webtoons/sync-all-webtoons/', admin_views.sync_all_webtoons_ajax, name='sync_all_webtoons_ajax'),
# ] 