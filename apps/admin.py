from django import forms
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.forms import UserChangeForm, UserCreationForm
from django.core.files.storage import default_storage
from django.core.validators import FileExtensionValidator
from django.utils.html import escape
from unfold.admin import ModelAdmin
from unfold.contrib.filters.admin import (
    ChoicesDropdownFilter,
    MultipleRelatedDropdownFilter,
    RangeDateFilter,
    RangeNumericFilter,
)

from apps.models import Credit, Genre, Movie, MovieRating, MovieReview, Person, User, WatchlistItem


class CustomUserCreationForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = User
        fields = ('phone_number', 'full_name', 'email')


@admin.register(User)
class UserAdmin(BaseUserAdmin, ModelAdmin):
    add_form = CustomUserCreationForm
    form = UserChangeForm
    model = User

    list_display = ['full_name', 'phone_number', 'email', 'is_staff']
    search_fields = ['full_name', 'phone_number', 'email']
    list_filter = ['is_staff', 'is_superuser', 'is_active']
    ordering = ('phone_number',)
    readonly_fields = ['last_login', 'date_joined']

    fieldsets = (
        (None, {'fields': ('phone_number', 'password')}),
        ('Shaxsiy ma\'lumot', {'fields': ('full_name', 'email', 'avatar')}),
        ('Ruxsatlar', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Muhim sanalar', {'fields': ('last_login', 'date_joined')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('phone_number', 'full_name', 'email', 'password1', 'password2'),
        }),
    )


@admin.register(Genre)
class GenreAdmin(ModelAdmin):
    list_display = ['name', 'slug']
    prepopulated_fields = {'slug': ('name',)}


class MovieRatingInline(admin.TabularInline):
    model = MovieRating
    extra = 0
    readonly_fields = ['value', 'user', 'created_at']
    can_delete = False


class CreditInline(admin.TabularInline):
    model = Credit
    extra = 1
    autocomplete_fields = ['person']


class MovieAdminForm(forms.ModelForm):
    storage = default_storage

    trailer_upload = forms.FileField(
        required=False,
        label='Treyler faylni yuklash',
        help_text='mp4 / webm / mov / ogg — fayl tanlasangiz, "Video URL" avtomatik to\'ldiriladi.',
        validators=[FileExtensionValidator(allowed_extensions=['mp4', 'webm', 'mov', 'ogg'])],
    )

    class Meta:
        model = Movie
        fields = '__all__'

    def clean_trailer_upload(self):
        trailer = self.cleaned_data.get('trailer_upload')
        if trailer:
            max_size = 500 * 1024 * 1024
            if trailer.size > max_size:
                raise forms.ValidationError('Fayl o\'lchami 500MB dan katta bo\'lmasligiga ruxsat yoq.')
        return trailer

    def clean_video_url(self):
        value = self.cleaned_data.get('video_url')
        if value is not None:
            value = value.strip()
            return value or None
        return value

    def save(self, commit=True):
        trailer = self.cleaned_data.get('trailer_upload')
        if trailer:
            storage = self.storage
            name = storage.save(f'trailers/{trailer.name}', trailer)
            url = storage.url(name)
            if url and not url.startswith(('http://', 'https://')):
                url = '/' + url.lstrip('/')
            if url:
                self.instance.video_url = url
        instance = super().save(commit=commit)
        return instance


@admin.register(Movie)
class MovieAdmin(ModelAdmin):
    form = MovieAdminForm
    list_display = ['title', 'release_date', 'rating', 'rating_count', 'views_count', 'status']
    list_filter = [
        ('status', ChoicesDropdownFilter),
        ('genres', MultipleRelatedDropdownFilter),
        ('release_date', RangeDateFilter),
        ('rating', RangeNumericFilter),
    ]
    search_fields = ['title', 'original_title', 'description']
    prepopulated_fields = {'slug': ('title',)}
    fieldsets = (
        (None, {'fields': ('title', 'original_title', 'slug', 'description', 'status')}),
        ('Kino ma\'lumotlari', {
            'fields': ('release_date', 'duration_minutes', 'poster', 'banner', 'video_url', 'trailer_upload'),
        }),
        ('Metama\'lumotlar', {
            'fields': ('certificate', 'language', 'country', 'studio', 'budget', 'box_office', 'views_count'),
        }),
        ('Janrlar', {'fields': ('genres',)}),
    )
    filter_horizontal = ['genres']
    readonly_fields = ['rating', 'rating_count', 'search_text']
    inlines = [CreditInline, MovieRatingInline]


@admin.register(Person)
class PersonAdmin(ModelAdmin):
    list_display = ['full_name', 'birth_date', 'birth_place', 'photo']
    search_fields = ['full_name']
    prepopulated_fields = {'slug': ('full_name',)}
    fieldsets = (
        (None, {'fields': ('full_name', 'slug', 'photo')}),
        ('Ma\'lumot', {'fields': ('bio', 'birth_date', 'birth_place')}),
    )
    inlines = [CreditInline]


@admin.register(WatchlistItem)
class WatchlistItemAdmin(ModelAdmin):
    list_display = ['user', 'movie', 'created_at']
    search_fields = ['user__full_name', 'movie__title']
    list_filter = [('movie__status', ChoicesDropdownFilter)]
    ordering = ['-created_at']
    list_select_related = ('user', 'movie')


@admin.register(MovieRating)
class MovieRatingAdmin(ModelAdmin):
    list_display = ['user', 'movie', 'value', 'created_at']
    search_fields = ['user__full_name', 'movie__title']
    list_filter = [('created_at', RangeDateFilter)]
    readonly_fields = ['value', 'created_at']
    ordering = ['-created_at']
    list_select_related = ('user', 'movie')


@admin.register(MovieReview)
class MovieReviewAdmin(ModelAdmin):
    list_display = ['user', 'movie', 'short_text', 'created_at']
    search_fields = ['user__full_name', 'movie__title', 'text']
    list_filter = [('created_at', RangeDateFilter)]
    ordering = ['-created_at']
    list_select_related = ('user', 'movie')

    @admin.display(description='Matn')
    def short_text(self, obj):
        text = escape(obj.text[:60])
        suffix = '...' if len(obj.text) > 60 else ''
        return text + suffix


@admin.register(Credit)
class CreditAdmin(ModelAdmin):
    list_display = ['movie', 'person', 'role', 'character_name']
    search_fields = ['movie__title', 'person__full_name']
    list_filter = ['role']
    autocomplete_fields = ['movie', 'person']
