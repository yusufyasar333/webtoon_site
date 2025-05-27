from django import forms
from django.utils.text import slugify
from django.forms import inlineformset_factory
from .models import Webtoon, Category, Chapter, ChapterImage

class WebtoonForm(forms.ModelForm):
    GENRE_CHOICES = [
        ('fantastik', 'Fantastik'),
        ('bilimkurgu', 'Bilimkurgu'),
        ('isekai', 'Isekai'),
        ('reankarnasyon', 'Reankarnasyon'),
        ('murim', 'Murim'),
    ]
    
    categories = forms.MultipleChoiceField(
        choices=GENRE_CHOICES,
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input'}),
        label="Türler"
    )
    
    class Meta:
        model = Webtoon
        fields = ['title', 'author', 'artist', 'description', 'thumbnail', 'categories', 'status', 'published']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 5, 'class': 'form-control'}),
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'author': forms.TextInput(attrs={'class': 'form-control'}),
            'artist': forms.TextInput(attrs={'class': 'form-control'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'thumbnail': forms.FileInput(attrs={'class': 'form-control'}),
            'published': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Eğer nesne düzenleniyorsa, mevcut kategorileri işaretle
        if self.instance.pk:
            current_categories = self.instance.categories.all()
            current_slugs = [category.slug for category in current_categories]
            self.initial['categories'] = current_slugs
    
    def save(self, commit=True):
        instance = super().save(commit=False)
        if not instance.slug:
            instance.slug = slugify(instance.title)
            
            # Slug benzersiz olmalı
            from django.db.models import Q
            counter = 1
            original_slug = instance.slug
            while Webtoon.objects.filter(Q(slug=instance.slug) & ~Q(pk=instance.pk)).exists():
                instance.slug = f"{original_slug}-{counter}"
                counter += 1
        
        # Önce kaydet, sonra kategorileri ekle
        if commit:
            instance.save()
            
            # Mevcut kategorileri temizle
            instance.categories.clear()
            
            # Seçilen kategorileri ekle
            selected_slugs = self.cleaned_data['categories']
            for slug in selected_slugs:
                # Önce kategoriyi oluştur veya bul
                category, created = Category.objects.get_or_create(
                    slug=slug,
                    defaults={'name': dict(self.GENRE_CHOICES).get(slug, slug.capitalize())}
                )
                instance.categories.add(category)
        
        return instance

class ChapterForm(forms.ModelForm):
    class Meta:
        model = Chapter
        fields = ['title', 'number', 'release_date', 'published']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'number': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.1'}),
            'release_date': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control'}),
            'published': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

class ChapterImageForm(forms.ModelForm):
    class Meta:
        model = ChapterImage
        fields = ['image', 'order']
        widgets = {
            'image': forms.FileInput(attrs={'class': 'form-control'}),
            'order': forms.HiddenInput(),
        }

# Formset - tek seferde birden fazla resim yükleme
ChapterImageFormSet = inlineformset_factory(
    Chapter,
    ChapterImage,
    form=ChapterImageForm,
    extra=20,
    max_num=100,
    can_delete=True
) 