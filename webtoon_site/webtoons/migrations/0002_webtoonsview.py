# Generated by Django 5.2.1 on 2025-05-27 18:26

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('webtoons', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='WebtoonsView',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('ip_address', models.GenericIPAddressField(blank=True, null=True)),
                ('viewed_at', models.DateTimeField(auto_now_add=True)),
                ('user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
                ('webtoon', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='views_log', to='webtoons.webtoon')),
            ],
            options={
                'unique_together': {('ip_address', 'webtoon'), ('user', 'webtoon')},
            },
        ),
    ]
