from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import JsonResponse, Http404
from django.db.models import Avg, Count, F, Q
from django.utils import timezone
from django.utils.text import slugify
from django.contrib import messages
from django.views.decorators.http import require_POST
from django.contrib.auth.forms import UserCreationForm
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.urls import reverse
from django.contrib.auth.models import User
from django.contrib.auth import login, authenticate
from .models import (
    Category, Webtoon, Chapter, ChapterImage, Comment, Rating, Bookmark, ReadingHistory,
    ExternalSource, ImportedWebtoon, ImportedChapter, ImportLog
)
from .forms import WebtoonForm, ChapterForm, ChapterImageFormSet, ImportWebtoonForm
from .services import import_webtoon_from_source, sync_webtoon_chapters
from .tasks import sync_webtoon, sync_all_auto_webtoons
import logging
import socket
import datetime
from django.core.management import call_command
from io import StringIO

def home(request):
    """Ana sayfa görünümü"""
    latest_webtoons = Webtoon.objects.filter(published=True).order_by('-created_date')[:12]
    popular_webtoons = Webtoon.objects.filter(published=True).order_by('-views')[:12]
    categories = Category.objects.all()
    
    context = {
        'latest_webtoons': latest_webtoons,
        'popular_webtoons': popular_webtoons,
        'categories': categories,
    }
    return render(request, 'webtoons/home.html', context)

def browse(request):
    """Tüm webtoonları görüntüleme"""
    webtoons = Webtoon.objects.filter(published=True)
    
    # Filtreleme
    category = request.GET.get('category')
    status = request.GET.get('status')
    sort = request.GET.get('sort', '-created_date')
    
    if category:
        webtoons = webtoons.filter(categories__slug=category)
    
    if status:
        webtoons = webtoons.filter(status=status)
    
    # Sıralama
    webtoons = webtoons.order_by(sort)
    
    # Sayfalama
    paginator = Paginator(webtoons, 24)  # Her sayfada 24 webtoon
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    categories = Category.objects.all()
    
    context = {
        'page_obj': page_obj,
        'categories': categories,
        'current_category': category,
        'current_status': status,
        'current_sort': sort,
    }
    return render(request, 'webtoons/browse.html', context)

def latest(request):
    """En son eklenen webtoonlar"""
    webtoons = Webtoon.objects.filter(published=True).order_by('-created_date')
    
    # Sayfalama
    paginator = Paginator(webtoons, 24)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'title': 'En Son Eklenenler',
    }
    return render(request, 'webtoons/webtoon_list.html', context)

def popular(request):
    """En popüler webtoonlar"""
    webtoons = Webtoon.objects.filter(published=True).order_by('-views')
    
    # Sayfalama
    paginator = Paginator(webtoons, 24)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'title': 'En Popüler',
    }
    return render(request, 'webtoons/webtoon_list.html', context)

def category_list(request):
    """Tüm kategorileri listele"""
    categories = Category.objects.annotate(webtoon_count=Count('webtoons'))
    
    context = {
        'categories': categories,
    }
    return render(request, 'webtoons/category_list.html', context)

def category_detail(request, slug):
    """Belirli bir kategorideki webtoonları görüntüle"""
    category = get_object_or_404(Category, slug=slug)
    webtoons = category.webtoons.filter(published=True)
    
    # Sayfalama
    paginator = Paginator(webtoons, 24)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'category': category,
        'page_obj': page_obj,
    }
    return render(request, 'webtoons/category_detail.html', context)

def webtoon_detail(request, slug):
    """Webtoon detay sayfası"""
    webtoon = get_object_or_404(Webtoon, slug=slug, published=True)
    chapters = webtoon.chapters.filter(published=True).order_by('number')
    
    # Görüntülenme sayısını artır
    webtoon.views += 1
    webtoon.save()
    
    # Ortalama puanı hesapla
    avg_rating = webtoon.ratings.aggregate(Avg('score'))['score__avg'] or 0
    
    # Kullanıcının yer işareti ve puanlaması
    user_bookmark = None
    user_rating = None
    if request.user.is_authenticated:
        user_bookmark = Bookmark.objects.filter(user=request.user, webtoon=webtoon).exists()
        try:
            user_rating = Rating.objects.get(user=request.user, webtoon=webtoon).score
        except Rating.DoesNotExist:
            pass
    
    # Yorumlar
    comments = webtoon.comments.filter(chapter__isnull=True).order_by('-created_date')[:20]
    
    context = {
        'webtoon': webtoon,
        'chapters': chapters,
        'avg_rating': avg_rating,
        'user_bookmark': user_bookmark,
        'user_rating': user_rating,
        'comments': comments,
    }
    return render(request, 'webtoons/webtoon_detail.html', context)

# IP adresini almak için yardımcı fonksiyon
def get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip

def chapter_detail(request, slug, number):
    """Bölüm okuma sayfası"""
    webtoon = get_object_or_404(Webtoon, slug=slug, published=True)
    chapter = get_object_or_404(Chapter, webtoon=webtoon, number=float(number), published=True)
    
    # Önceki ve sonraki bölümleri bul
    prev_chapter = Chapter.objects.filter(
        webtoon=webtoon, number__lt=float(number), published=True
    ).order_by('-number').first()
    
    next_chapter = Chapter.objects.filter(
        webtoon=webtoon, number__gt=float(number), published=True
    ).order_by('number').first()
    
    # Okuma geçmişine ekle
    if request.user.is_authenticated:
        ReadingHistory.objects.update_or_create(
            user=request.user,
            chapter=chapter,
        )
    
    # Bölüm yorumları
    comments = chapter.comments.order_by('-created_date')[:20]
    
    context = {
        'webtoon': webtoon,
        'chapter': chapter,
        'prev_chapter': prev_chapter,
        'next_chapter': next_chapter,
        'comments': comments,
    }
    return render(request, 'webtoons/chapter_detail.html', context)

@login_required
def user_profile(request):
    """Kullanıcı profil sayfası"""
    return render(request, 'webtoons/user_profile.html')

@login_required
def user_bookmarks(request):
    """Kullanıcının yer işaretleri"""
    bookmarks = Bookmark.objects.filter(user=request.user).order_by('-created_date')
    
    context = {
        'bookmarks': bookmarks,
    }
    return render(request, 'webtoons/user_bookmarks.html', context)

@login_required
def user_history(request):
    """Kullanıcının okuma geçmişi"""
    history = ReadingHistory.objects.filter(user=request.user).order_by('-last_read')
    
    context = {
        'history': history,
    }
    return render(request, 'webtoons/user_history.html', context)

@login_required
@require_POST
def toggle_bookmark(request, webtoon_id):
    """Yer işaretini ekle/kaldır"""
    webtoon = get_object_or_404(Webtoon, id=webtoon_id)
    bookmark, created = Bookmark.objects.get_or_create(user=request.user, webtoon=webtoon)
    
    if not created:
        bookmark.delete()
        is_bookmarked = False
    else:
        is_bookmarked = True
    
    return JsonResponse({'is_bookmarked': is_bookmarked})

@login_required
@require_POST
def rate_webtoon(request, webtoon_id):
    """Webtoon puanlama"""
    webtoon = get_object_or_404(Webtoon, id=webtoon_id)
    score = int(request.POST.get('score', 0))
    
    if score < 1 or score > 10:
        return JsonResponse({'error': 'Geçersiz puan'}, status=400)
    
    rating, created = Rating.objects.update_or_create(
        user=request.user,
        webtoon=webtoon,
        defaults={'score': score}
    )
    
    avg_rating = webtoon.ratings.aggregate(Avg('score'))['score__avg'] or 0
    
    return JsonResponse({
        'score': score,
        'avg_rating': round(avg_rating, 1)
    })

@login_required
@require_POST
def add_comment(request):
    """Yorum ekleme"""
    webtoon_id = request.POST.get('webtoon_id')
    chapter_id = request.POST.get('chapter_id')
    content = request.POST.get('content')
    
    if not content or not webtoon_id:
        return JsonResponse({'error': 'Geçersiz veri'}, status=400)
    
    webtoon = get_object_or_404(Webtoon, id=webtoon_id)
    chapter = None
    if chapter_id:
        chapter = get_object_or_404(Chapter, id=chapter_id)
    
    comment = Comment.objects.create(
        user=request.user,
        webtoon=webtoon,
        chapter=chapter,
        content=content
    )
    
    return JsonResponse({
        'id': comment.id,
        'username': comment.user.username,
        'content': comment.content,
        'created_date': comment.created_date.strftime('%d.%m.%Y %H:%M')
    })

def search(request):
    """Arama fonksiyonu"""
    query = request.GET.get('q', '').strip()
    
    if query:
        # Daha güçlü arama
        webtoons = Webtoon.objects.filter(
            Q(title__icontains=query) | 
            Q(author__icontains=query) |
            Q(artist__icontains=query) |
            Q(description__icontains=query) |
            Q(slug__icontains=query) |
            Q(categories__name__icontains=query) |
            Q(categories__slug__icontains=query)
        ).filter(published=True).distinct()
        
        # Debug için arama sonuçlarını loglayalım
        print(f"Arama sorgusu: '{query}' - {webtoons.count()} sonuç")
        for w in webtoons:
            print(f"- {w.title} (ID: {w.id}, Slug: {w.slug})")
    else:
        webtoons = Webtoon.objects.none()
    
    # Sayfalama
    paginator = Paginator(webtoons, 24)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'query': query,
        'page_obj': page_obj,
        'webtoons': page_obj,  # Template'de webtoons değişkeni kullanılıyor
        'result_count': webtoons.count(),
    }
    return render(request, 'webtoons/search_results.html', context)

# Admin kontrol paneli

def is_admin(user):
    return user.is_authenticated and (user.is_staff or user.is_superuser)

@user_passes_test(is_admin)
def admin_dashboard(request):
    """Yönetici kontrol paneli"""
    webtoons_count = Webtoon.objects.count()
    chapters_count = Chapter.objects.count()
    categories_count = Category.objects.count()
    users_count = User.objects.count()
    
    recent_webtoons = Webtoon.objects.order_by('-created_date')[:5]
    recent_comments = Comment.objects.order_by('-created_date')[:5]
    
    context = {
        'webtoons_count': webtoons_count,
        'chapters_count': chapters_count,
        'categories_count': categories_count,
        'users_count': users_count,
        'recent_webtoons': recent_webtoons,
        'recent_comments': recent_comments,
    }
    return render(request, 'webtoons/admin/dashboard.html', context)

@user_passes_test(is_admin)
def admin_webtoon_list(request):
    """Webtoon listesi yönetimi"""
    webtoons = Webtoon.objects.all().order_by('-created_date')
    
    context = {
        'webtoons': webtoons,
    }
    return render(request, 'webtoons/admin/webtoon_list.html', context)

@user_passes_test(is_admin)
def admin_webtoon_create(request):
    """Webtoon oluşturma"""
    # Önce kategorilerin varlığını kontrol et
    required_categories = [
        {"name": "Fantastik", "slug": "fantastik"},
        {"name": "Bilimkurgu", "slug": "bilimkurgu"},
        {"name": "Isekai", "slug": "isekai"},
        {"name": "Reankarnasyon", "slug": "reankarnasyon"},
        {"name": "Murim", "slug": "murim"},
    ]
    
    for cat in required_categories:
        Category.objects.get_or_create(name=cat["name"], slug=cat["slug"])
    
    if request.method == 'POST':
        form = WebtoonForm(request.POST, request.FILES)
        if form.is_valid():
            webtoon = form.save()
            messages.success(request, 'Webtoon başarıyla oluşturuldu.')
            return redirect('webtoons:admin_webtoon_detail', slug=webtoon.slug)
    else:
        form = WebtoonForm()
    
    context = {
        'form': form,
        'title': 'Yeni Webtoon Ekle',
    }
    return render(request, 'webtoons/admin/webtoon_form.html', context)

@user_passes_test(is_admin)
def admin_webtoon_edit(request, slug):
    """Webtoon düzenleme"""
    # Önce kategorilerin varlığını kontrol et
    required_categories = [
        {"name": "Fantastik", "slug": "fantastik"},
        {"name": "Bilimkurgu", "slug": "bilimkurgu"},
        {"name": "Isekai", "slug": "isekai"},
        {"name": "Reankarnasyon", "slug": "reankarnasyon"},
        {"name": "Murim", "slug": "murim"},
    ]
    
    for cat in required_categories:
        Category.objects.get_or_create(name=cat["name"], slug=cat["slug"])
    
    webtoon = get_object_or_404(Webtoon, slug=slug)
    
    if request.method == 'POST':
        form = WebtoonForm(request.POST, request.FILES, instance=webtoon)
        if form.is_valid():
            form.save()
            messages.success(request, 'Webtoon başarıyla güncellendi.')
            return redirect('webtoons:admin_webtoon_detail', slug=webtoon.slug)
    else:
        form = WebtoonForm(instance=webtoon)
    
    context = {
        'form': form,
        'webtoon': webtoon,
        'title': f'{webtoon.title} - Düzenle',
    }
    return render(request, 'webtoons/admin/webtoon_form.html', context)

@user_passes_test(is_admin)
def admin_webtoon_detail(request, slug):
    """Webtoon detayı ve bölüm yönetimi"""
    webtoon = get_object_or_404(Webtoon, slug=slug)
    chapters = webtoon.chapters.all().order_by('number')
    
    context = {
        'webtoon': webtoon,
        'chapters': chapters,
    }
    return render(request, 'webtoons/admin/webtoon_detail.html', context)

@user_passes_test(is_admin)
def admin_webtoon_delete(request, slug):
    """Webtoon silme"""
    webtoon = get_object_or_404(Webtoon, slug=slug)
    
    if request.method == 'POST':
        webtoon.delete()
        messages.success(request, 'Webtoon başarıyla silindi.')
        return redirect('webtoons:admin_webtoon_list')
    
    context = {
        'webtoon': webtoon,
    }
    return render(request, 'webtoons/admin/webtoon_delete.html', context)

@user_passes_test(is_admin)
def admin_chapter_create(request, slug):
    """Bölüm oluşturma"""
    webtoon = get_object_or_404(Webtoon, slug=slug)
    
    if request.method == 'POST':
        form = ChapterForm(request.POST)
        formset = ChapterImageFormSet(request.POST, request.FILES, prefix='images')
        
        if form.is_valid() and formset.is_valid():
            chapter = form.save(commit=False)
            chapter.webtoon = webtoon
            chapter.save()
            
            # Formset kaydetme
            images = formset.save(commit=False)
            for i, image in enumerate(images):
                image.chapter = chapter
                # Sıralama indeksi form'dan gelecek
                if not image.order and image.order != 0:  # Eğer order belirtilmemişse
                    image.order = i
                image.save()
            
            # Silinen resimleri temizle
            for obj in formset.deleted_objects:
                obj.delete()
            
            messages.success(request, f'Bölüm {chapter.number} başarıyla oluşturuldu.')
            return redirect('webtoons:admin_webtoon_detail', slug=webtoon.slug)
    else:
        form = ChapterForm()
        formset = ChapterImageFormSet(prefix='images')
    
    context = {
        'form': form,
        'formset': formset,
        'webtoon': webtoon,
        'title': f'{webtoon.title} - Yeni Bölüm Ekle',
    }
    return render(request, 'webtoons/admin/chapter_form.html', context)

@user_passes_test(is_admin)
def admin_chapter_edit(request, slug, number):
    """Bölüm düzenleme"""
    webtoon = get_object_or_404(Webtoon, slug=slug)
    chapter = get_object_or_404(Chapter, webtoon=webtoon, number=float(number))
    
    if request.method == 'POST':
        form = ChapterForm(request.POST, instance=chapter)
        formset = ChapterImageFormSet(request.POST, request.FILES, prefix='images', instance=chapter)
        
        if form.is_valid() and formset.is_valid():
            form.save()
            
            # Formset kaydetme
            images = formset.save(commit=False)
            for i, image in enumerate(images):
                image.chapter = chapter
                # Sıralama indeksi form'dan gelecek
                if not image.order and image.order != 0:  # Eğer order belirtilmemişse
                    image.order = i
                image.save()
            
            # Silinen resimleri temizle
            for obj in formset.deleted_objects:
                obj.delete()
            
            messages.success(request, f'Bölüm {chapter.number} başarıyla güncellendi.')
            return redirect('webtoons:admin_webtoon_detail', slug=webtoon.slug)
    else:
        form = ChapterForm(instance=chapter)
        formset = ChapterImageFormSet(prefix='images', instance=chapter)
    
    context = {
        'form': form,
        'formset': formset,
        'webtoon': webtoon,
        'chapter': chapter,
        'title': f'{webtoon.title} - Bölüm {chapter.number} - Düzenle',
    }
    return render(request, 'webtoons/admin/chapter_form.html', context)

@user_passes_test(is_admin)
def admin_chapter_delete(request, slug, number):
    """Bölüm silme"""
    webtoon = get_object_or_404(Webtoon, slug=slug)
    chapter = get_object_or_404(Chapter, webtoon=webtoon, number=float(number))
    
    if request.method == 'POST':
        chapter.delete()
        messages.success(request, f'Bölüm {chapter.number} başarıyla silindi.')
        return redirect('webtoons:admin_webtoon_detail', slug=webtoon.slug)
    
    context = {
        'webtoon': webtoon,
        'chapter': chapter,
    }
    return render(request, 'webtoons/admin/chapter_delete.html', context)

@user_passes_test(is_admin)
def admin_category_list(request):
    """Kategori listesi ve ekleme"""
    categories = Category.objects.all().order_by('name')
    
    # Ensure specific categories exist
    required_categories = [
        {"name": "Fantastik", "slug": "fantastik"},
        {"name": "Bilimkurgu", "slug": "bilimkurgu"},
        {"name": "Isekai", "slug": "isekai"},
        {"name": "Reankarnasyon", "slug": "reankarnasyon"},
        {"name": "Murim", "slug": "murim"},
    ]
    
    for cat in required_categories:
        Category.objects.get_or_create(name=cat["name"], slug=cat["slug"])
    
    # Refresh categories after ensuring required ones exist
    categories = Category.objects.all().order_by('name')
    
    # Yeni kategori formu
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        
        if name:
            category_slug = slugify(name)
            if Category.objects.filter(slug=category_slug).exists():
                messages.error(request, 'Bu kategori zaten mevcut.')
            else:
                Category.objects.create(name=name, slug=category_slug)
                messages.success(request, 'Kategori başarıyla eklendi.')
                return redirect('webtoons:admin_category_list')
        else:
            messages.error(request, 'Kategori adı boş olamaz.')
    
    context = {
        'categories': categories,
    }
    return render(request, 'webtoons/admin/category_list.html', context)

@user_passes_test(is_admin)
def admin_category_edit(request, slug):
    """Kategori düzenleme"""
    category = get_object_or_404(Category, slug=slug)
    
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        description = request.POST.get('description', '').strip()
        
        if name:
            # Eğer aynı isimli kategori varsa ve bu kategori değilse kontrol et
            category_slug = slugify(name)
            if category_slug != category.slug and Category.objects.filter(slug=category_slug).exists():
                messages.error(request, 'Bu kategori adı zaten kullanılıyor.')
            else:
                category.name = name
                category.description = description
                category.slug = category_slug
                category.save()
                messages.success(request, 'Kategori başarıyla güncellendi.')
                return redirect('webtoons:admin_category_list')
        else:
            messages.error(request, 'Kategori adı boş olamaz.')
    
    context = {
        'category': category,
    }
    return render(request, 'webtoons/admin/category_edit.html', context)

@user_passes_test(is_admin)
def admin_category_delete(request, slug):
    """Kategori silme"""
    category = get_object_or_404(Category, slug=slug)
    
    if request.method == 'POST':
        # Eğer kategoride webtoon varsa uyarı göster
        if category.webtoons.exists():
            messages.error(request, 'Bu kategoride webtoonlar bulunduğu için silinemez. Önce bu webtoonları başka kategorilere taşımalısınız.')
            return redirect('webtoons:admin_category_list')
        
        category.delete()
        messages.success(request, 'Kategori başarıyla silindi.')
        return redirect('webtoons:admin_category_list')
    
    context = {
        'category': category,
        'has_webtoons': category.webtoons.exists(),
    }
    return render(request, 'webtoons/admin/category_delete.html', context)

def register(request):
    """Kullanıcı kayıt sayfası"""
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password1')
            user = authenticate(username=username, password=password)
            login(request, user)
            messages.success(request, f'Hesabınız başarıyla oluşturuldu!')
            return redirect('webtoons:home')
    else:
        form = UserCreationForm()
    
    context = {
        'form': form,
        'title': 'Kayıt Ol',
    }
    return render(request, 'webtoons/register.html', context)

@user_passes_test(is_admin)
def admin_import_webtoon(request):
    """Webtoon içeri aktarma sayfası"""
    if request.method == 'POST':
        form = ImportWebtoonForm(request.POST)
        if form.is_valid():
            source_url = form.cleaned_data['source_url']
            source_name = form.cleaned_data['source_name']
            max_chapters = form.cleaned_data['max_chapters']
            
            # İçeri aktarma işlemini başlat
            result = import_webtoon_from_source(
                source_url=source_url,
                source_name=source_name,
                auto_sync=True,  # Sabit değer olarak True kullanıyoruz
                max_chapters=max_chapters
            )
            
            if result['success']:
                messages.success(request, result['message'])
                if 'imported_webtoon' in result and 'webtoon' in result:
                    return redirect('webtoons:admin_webtoon_detail', slug=result['webtoon'].slug)
                return redirect('webtoons:admin_webtoon_list')
            else:
                messages.error(request, result['message'])
    else:
        form = ImportWebtoonForm()
    
    # Son içeri aktarma loglarını göster
    recent_logs = ImportLog.objects.all().order_by('-start_time')[:10]
    
    return render(request, 'webtoons/admin/import_webtoon.html', {
        'form': form,
        'recent_logs': recent_logs,
        'title': 'Webtoon İçeri Aktar',
    })

@user_passes_test(is_admin)
def admin_sync_webtoons(request):
    """Webtoon senkronizasyon sayfası"""
    # Logger'ı başlangıçta tanımla
    logger = logging.getLogger(__name__)
    
    # Otomatik senkronizasyon açık olan webtoonları bul
    auto_sync_webtoons = ImportedWebtoon.objects.filter(auto_sync=True)
    
    # Tüm içeri aktarılmış webtoonları bul
    all_imported_webtoons = ImportedWebtoon.objects.all()
    
    # Aktif kaynakları bul
    active_sources = ExternalSource.objects.filter(active=True)
    
    # Son senkronizasyon loglarını göster
    recent_logs = ImportLog.objects.all().order_by('-start_time')[:10]
    
    # URL'den veya POST'tan gelen senkronizasyon işlemi
    webtoon_id = request.POST.get('webtoon_id') or request.GET.get('webtoon_id')
    max_chapters = request.POST.get('max_chapters') or request.GET.get('max_chapters')
    
    if webtoon_id:
        try:
            imported_webtoon = ImportedWebtoon.objects.get(id=webtoon_id)
            
            # Maksimum bölüm sayısını kontrol et
            if max_chapters:
                try:
                    max_chapters = int(max_chapters)
                    logger.info(f"Maksimum bölüm sayısı belirlendi: {max_chapters}")
                except (ValueError, TypeError):
                    max_chapters = None
                    logger.warning(f"Geçersiz maksimum bölüm sayısı: {request.POST.get('max_chapters')}")
            else:
                max_chapters = None
                logger.info("Maksimum bölüm sayısı belirtilmemiş, tüm bölümler çekilecek.")
            
            # Senkronizasyonu başlat
            result = sync_webtoon_chapters(imported_webtoon, max_chapters)
            
            if result.get('success', False):
                new_chapters = result.get('new_chapters', 0)
                if new_chapters > 0:
                    messages.success(request, f"{new_chapters} yeni bölüm senkronize edildi.")
                else:
                    messages.info(request, "Yeni bölüm bulunamadı.")
            else:
                messages.error(request, f"Senkronizasyon hatası: {result.get('message', 'Bilinmeyen hata')}")
                
            # Aynı sayfada kal
            return redirect('webtoons:admin_sync_webtoons')
        except ImportedWebtoon.DoesNotExist:
            messages.error(request, "Belirtilen webtoon bulunamadı.")
        except Exception as e:
            import traceback
            logger.error(f"Senkronizasyon hatası: {e}")
            logger.error(traceback.format_exc())
            messages.error(request, f"Senkronizasyon sırasında hata oluştu: {str(e)}")
    
    return render(request, 'webtoons/admin/sync_webtoons.html', {
        'auto_sync_webtoons': auto_sync_webtoons,
        'all_imported_webtoons': all_imported_webtoons,
        'active_sources': active_sources,
        'recent_logs': recent_logs,
        'title': 'Webtoon Senkronizasyonu',
    })

@user_passes_test(is_admin)
@require_POST
def admin_sync_webtoon_ajax(request, webtoon_id):
    """Belirli bir webtoon'u senkronize et (AJAX)"""
    imported_webtoon = get_object_or_404(ImportedWebtoon, id=webtoon_id)
    max_chapters = request.POST.get('max_chapters')
    
    if max_chapters and max_chapters.isdigit():
        max_chapters = int(max_chapters)
    else:
        max_chapters = None
    
    # Asenkron görevi başlat
    task = sync_webtoon.delay(webtoon_id, max_chapters)
    
    # Tarayıcıya hemen yanıt ver
    return JsonResponse({
        'success': True,
        'message': 'Senkronizasyon görevi başlatıldı',
        'task_id': task.id
    })

@user_passes_test(is_admin)
@require_POST
def admin_sync_all_webtoons_ajax(request):
    """Otomatik senkronizasyon açık olan tüm webtoonları senkronize et (AJAX)"""
    # Asenkron görevi başlat
    task = sync_all_auto_webtoons.delay()
    
    # Tarayıcıya hemen yanıt ver
    return JsonResponse({
        'success': True,
        'message': 'Tüm webtoonların senkronizasyon görevi başlatıldı',
        'task_id': task.id
    })

# Admin kontrolü
def is_staff(user):
    return user.is_staff

@login_required
@user_passes_test(is_staff)
def import_webtoon(request):
    """Dışarıdan webtoon içeri aktarma sayfası"""
    
    if request.method == 'POST':
        form = ImportWebtoonForm(request.POST)
        if form.is_valid():
            source_url = form.cleaned_data['source_url']
            source_name = form.cleaned_data['source_name']
            max_chapters = form.cleaned_data['max_chapters']
            
            # İçeri aktarma işlemini başlat
            result = import_webtoon_from_source(source_url, source_name, True, max_chapters)
            
            if result.get('success', False):
                messages.success(request, f"{result['webtoon'].title} başarıyla içeri aktarıldı. {result.get('imported_chapters', 0)} bölüm içeri aktarıldı.")
                return redirect('admin:webtoons_webtoon_change', result['webtoon'].id)
            else:
                messages.error(request, f"İçeri aktarma başarısız: {result.get('message', 'Bilinmeyen hata')}")
    else:
        # URL parametresi varsa form alanını doldur
        initial_data = {}
        if 'url' in request.GET:
            initial_data['source_url'] = request.GET.get('url')
        
        form = ImportWebtoonForm(initial=initial_data)
    
    # Mevcut kaynakları göster
    sources = ExternalSource.objects.all()
    
    # Son içeri aktarma loglarını göster
    recent_logs = ImportLog.objects.order_by('-start_time')[:10]
    
    return render(request, 'webtoons/import_webtoon.html', {
        'form': form,
        'sources': sources,
        'recent_logs': recent_logs,
        'title': 'İçeri Webtoon Aktar'
    })

@login_required
@user_passes_test(is_staff)
def check_source(request):
    """Kaynak URL'sini kontrol et ve bilgi getir"""
    url = request.GET.get('url', '')
    
    if not url:
        return JsonResponse({'error': 'URL belirtilmedi'})
    
    # URL'nin hangi siteye ait olduğunu belirle
    is_mangadex = "mangadex.org" in url.lower()
    is_mangazure = "mangazure.net" in url.lower()
    
    source_type = "MangaDex" if is_mangadex else "MangaZure" if is_mangazure else "Bilinmeyen Kaynak"
    
    return JsonResponse({
        'source_type': source_type,
        'valid': is_mangadex or is_mangazure,
        'message': f"Bu URL {source_type} sitesine ait görünüyor." if is_mangadex or is_mangazure else "Bu URL desteklenen bir kaynak sitesine ait değil."
    })

@user_passes_test(is_admin)
def admin_fix_chapters(request):
    """Bozuk veya yarım kalan bölümleri düzeltme sayfası"""
    from django.core.management import call_command
    from io import StringIO
    from django.db.models import Count
    
    # Bölüm sayısına göre webtoonları al
    webtoons = Webtoon.objects.annotate(chapter_count=Count('chapters')).order_by('-chapter_count')
    
    # Resmi olmayan bölümleri bul
    empty_chapters = Chapter.objects.annotate(
        image_count=Count('images')
    ).filter(
        image_count=0
    ).select_related('webtoon')
    
    # Bir webtoon'un boş bölümlerini temizle
    if request.method == 'POST' and 'webtoon_slug' in request.POST:
        webtoon_slug = request.POST.get('webtoon_slug')
        fix_empty = 'fix_empty' in request.POST
        clean_missing_images = 'clean_missing_images' in request.POST
        delete_orphaned = 'delete_orphaned' in request.POST
        
        # Yönetim komutunu çalıştır
        out = StringIO()
        try:
            call_command(
                'sync_media_database',
                webtoon_slug=webtoon_slug,
                fix_empty_chapters=fix_empty,
                clean_missing_images=clean_missing_images,
                delete_orphaned_media=delete_orphaned,
                stdout=out
            )
            output = out.getvalue()
            messages.success(request, f"İşlem tamamlandı. {webtoon_slug} için temizleme işlemi yapıldı.")
            messages.info(request, output)
        except Exception as e:
            messages.error(request, f"Hata oluştu: {str(e)}")
        
        return redirect('webtoons:admin_fix_chapters')
    
    return render(request, 'webtoons/admin/fix_chapters.html', {
        'webtoons': webtoons,
        'empty_chapters': empty_chapters,
        'empty_chapters_count': empty_chapters.count(),
        'title': 'Bozuk Bölümleri Düzelt',
    })
