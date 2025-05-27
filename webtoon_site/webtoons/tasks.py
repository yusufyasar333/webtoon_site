"""
Webtoon scraping için Celery görevleri
"""
from datetime import timedelta
from celery import shared_task
from django.utils import timezone
from .models import ImportedWebtoon, ImportLog
from .services import sync_webtoon_chapters

@shared_task
def sync_webtoon(webtoon_id, max_chapters=None):
    """
    Belirli bir webtoon'u senkronize et
    
    Args:
        webtoon_id (int): ImportedWebtoon ID
        max_chapters (int, optional): Maksimum bölüm sayısı
        
    Returns:
        dict: Senkronizasyon sonuçları
    """
    try:
        imported_webtoon = ImportedWebtoon.objects.get(id=webtoon_id)
        return sync_webtoon_chapters(imported_webtoon, max_new_chapters=max_chapters)
    except ImportedWebtoon.DoesNotExist:
        return {'success': False, 'message': f'Webtoon bulunamadı: {webtoon_id}'}
    except Exception as e:
        return {'success': False, 'message': f'Senkronizasyon hatası: {e}'}

@shared_task
def sync_all_auto_webtoons():
    """
    Otomatik senkronizasyon açık olan tüm webtoonları senkronize et
    
    Returns:
        dict: Senkronizasyon sonuçları
    """
    auto_sync_webtoons = ImportedWebtoon.objects.filter(auto_sync=True)
    results = []
    
    for imported_webtoon in auto_sync_webtoons:
        try:
            result = sync_webtoon_chapters(imported_webtoon)
            results.append({
                'webtoon': imported_webtoon.webtoon.title,
                'success': result['success'],
                'message': result['message'],
            })
        except Exception as e:
            results.append({
                'webtoon': imported_webtoon.webtoon.title,
                'success': False,
                'message': f'Hata: {e}',
            })
    
    return {'results': results}

@shared_task
def cleanup_old_logs():
    """
    Eski import ve senkronizasyon loglarını temizle
    
    Returns:
        int: Silinen log sayısı
    """
    # 30 günden eski logları sil
    cutoff_date = timezone.now() - timedelta(days=30)
    deleted_count, _ = ImportLog.objects.filter(start_time__lt=cutoff_date).delete()
    
    return deleted_count 