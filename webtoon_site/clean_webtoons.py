import os, sys, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webtoon_site.settings')
django.setup()

from django.conf import settings
from webtoons.models import Webtoon, ChapterImage
from django.db.models import Count

print('Webtoon silme islemi basliyor...')
w = Webtoon.objects.first()
if w:
    print(f'Siliniyor: {w.title}')
    w.delete()
    print('Silme islemi tamamlandi')
else:
    print('Silinecek webtoon bulunamadi')

