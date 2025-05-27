"""
Admin panel için özel view'lar
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.urls import reverse
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from .models import ImportedWebtoon, ImportLog, ExternalSource
from .services import import_webtoon_from_source, sync_webtoon_chapters
from .tasks import sync_webtoon, sync_all_auto_webtoons
from .forms import ImportWebtoonForm

@staff_member_required
def import_webtoon(request):
    """Webtoon içeri aktarma sayfası"""
    if request.method == 'POST':
        form = ImportWebtoonForm(request.POST)
        if form.is_valid():
            source_url = form.cleaned_data['source_url']
            source_name = form.cleaned_data['source_name']
            max_chapters = form.cleaned_data['max_chapters']
            auto_sync = form.cleaned_data['auto_sync']
            
            # İçeri aktarma işlemini başlat
            result = import_webtoon_from_source(
                source_url=source_url,
                source_name=source_name,
                auto_sync=auto_sync,
                max_chapters=max_chapters
            )
            
            if result['success']:
                messages.success(request, result['message'])
                if 'imported_webtoon' in result:
                    return redirect(
                        'admin:webtoons_importedwebtoon_change', 
                        result['imported_webtoon'].id
                    )
                return redirect('admin:webtoons_webtoon_changelist')
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
        'site_header': 'Webtoon Yönetimi'
    })

@staff_member_required
def sync_webtoons(request):
    """Webtoon senkronizasyon sayfası"""
    # Otomatik senkronizasyon açık olan webtoonları bul
    auto_sync_webtoons = ImportedWebtoon.objects.filter(auto_sync=True)
    
    # Tüm içeri aktarılmış webtoonları bul
    all_imported_webtoons = ImportedWebtoon.objects.all()
    
    # Aktif kaynakları bul
    active_sources = ExternalSource.objects.filter(active=True)
    
    # Son senkronizasyon loglarını göster
    recent_logs = ImportLog.objects.all().order_by('-start_time')[:10]
    
    return render(request, 'webtoons/admin/sync_webtoons.html', {
        'auto_sync_webtoons': auto_sync_webtoons,
        'all_imported_webtoons': all_imported_webtoons,
        'active_sources': active_sources,
        'recent_logs': recent_logs,
        'title': 'Webtoon Senkronizasyonu',
        'site_header': 'Webtoon Yönetimi'
    })

@staff_member_required
@require_POST
def sync_webtoon_ajax(request, webtoon_id):
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

@staff_member_required
@require_POST
def sync_all_webtoons_ajax(request):
    """Otomatik senkronizasyon açık olan tüm webtoonları senkronize et (AJAX)"""
    # Asenkron görevi başlat
    task = sync_all_auto_webtoons.delay()
    
    # Tarayıcıya hemen yanıt ver
    return JsonResponse({
        'success': True,
        'message': 'Tüm webtoonların senkronizasyon görevi başlatıldı',
        'task_id': task.id
    }) 