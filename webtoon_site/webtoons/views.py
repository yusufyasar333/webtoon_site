from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.db.models import Avg, Count, Q
from django.views.decorators.http import require_POST
from django.core.paginator import Paginator
from django.contrib import messages
from django.contrib.auth.decorators import user_passes_test
from django.contrib.auth.models import User
from .models import Category, Webtoon, Chapter, Comment, Rating, Bookmark, ReadingHistory, WebtoonsView
from .forms import WebtoonForm, ChapterForm, ChapterImageFormSet
from django.utils.text import slugify
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import login, authenticate

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
    
    # Görüntülenme sayısını artır - sadece yeni kullanıcı veya IP için
    try:
        if request.user.is_authenticated:
            # Kullanıcı giriş yapmışsa, kullanıcıya göre kontrol et
            view_obj, created = WebtoonsView.objects.get_or_create(
                webtoon=webtoon,
                user=request.user
            )
            if created:
                webtoon.views += 1
                webtoon.save()
        else:
            # Giriş yapmamış kullanıcılar için IP adresine göre kontrol et
            ip_address = get_client_ip(request)
            if ip_address:
                view_obj, created = WebtoonsView.objects.get_or_create(
                    webtoon=webtoon,
                    ip_address=ip_address,
                    user=None
                )
                if created:
                    webtoon.views += 1
                    webtoon.save()
    except Exception as e:
        # Hata durumunda sessizce devam et, görüntüleme sayısını güncelleme
        print(f"Görüntüleme kaydı hatası: {e}")
    
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
