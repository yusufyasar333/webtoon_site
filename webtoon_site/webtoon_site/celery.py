"""
Celery config for webtoon_site project.
"""
import os
from celery import Celery
from celery.schedules import crontab

# Django ayarlarını yükle
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webtoon_site.settings')

app = Celery('webtoon_site')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()

# Periyodik görevleri tanımla
app.conf.beat_schedule = {
    # Her gün gece yarısı çalışacak görev
    'sync-all-webtoons-daily': {
        'task': 'webtoons.tasks.sync_all_auto_webtoons',
        'schedule': crontab(minute=0, hour=0),  # Gece yarısı
    },
    # Her hafta Pazar günü çalışacak görev
    'cleanup-old-logs-weekly': {
        'task': 'webtoons.tasks.cleanup_old_logs',
        'schedule': crontab(minute=0, hour=1, day_of_week='sunday'),  # Pazar günü saat 01:00
    },
}

@app.task(bind=True)
def debug_task(self):
    """Debug task"""
    print(f'Request: {self.request!r}') 