import logging
import re
from pathlib import Path

from django.conf import settings
from django.contrib.auth.hashers import make_password
from django.contrib.auth.models import AbstractUser, UserManager
from django.db import models
from django.db.models import (
    Avg,
    CharField,
    Count,
    DateField,
    DateTimeField,
    DecimalField,
    F,
    ImageField,
    Model,
    PositiveBigIntegerField,
    PositiveIntegerField,
    TextChoices,
    TextField,
    URLField,
)
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from apps.utils import smart_convert, to_latin

logger = logging.getLogger(__name__)

def _storage_has(storage, name):
    try:
        return storage.exists(name)
    except NotImplementedError:
        return False


def _image_changed(instance, field_name):
    """Rasm fayli yangidan yuklanganini aniqlaydi (DB dagi nom bilan solishtirib)."""
    current = getattr(instance, field_name)
    name = getattr(current, 'name', '') if hasattr(current, 'name') else ''
    if not instance.pk:
        return bool(name)
    old = type(instance).objects.filter(pk=instance.pk).values_list(field_name, flat=True).first()
    return name != (old or '')


class CustomUserManager(UserManager):
    def _create_user_object(self, phone_number, raw_secret, email, **extra_fields):
        if not phone_number:
            raise ValueError("The given phone_number must be set")
        user = self.model(phone_number=phone_number, **extra_fields)
        if email:
            user.email = email
        if raw_secret:
            user.password = make_password(raw_secret)
        else:
            user.set_unusable_password()
        return user

    def _create_user(self, phone_number, raw_secret, email, **extra_fields):
        user = self._create_user_object(phone_number, raw_secret, email, **extra_fields)
        user.save(using=self._db)
        return user

    def create_user(self, phone_number, *args, email=None, **extra_fields):
        raw_secret = extra_fields.pop('password', None)
        if args:
            raw_secret = args[0]
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(phone_number, raw_secret, email, **extra_fields)

    def create_superuser(self, phone_number, *args, email=None, **extra_fields):
        raw_secret = extra_fields.pop('password', None)
        if args:
            raw_secret = args[0]
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")

        return self._create_user(phone_number, raw_secret, email, **extra_fields)


class User(AbstractUser):
    first_name = None
    last_name = None
    username = None
    full_name = CharField(max_length=255)
    phone_number = CharField(max_length=20, unique=True)
    avatar = ImageField(upload_to='avatars/', null=True, blank=True)
    REQUIRED_FIELDS = ['full_name']
    USERNAME_FIELD = 'phone_number'
    objects = CustomUserManager()

    def __str__(self):
        return f"{self.full_name} ({self.phone_number})"

    def save(self, *args, **kwargs):
        if self.avatar and _image_changed(self, 'avatar'):
            smart_convert(self, 'avatar', (400, 400))
        super().save(*args, **kwargs)


class Genre(Model):
    name = CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True)

    def __str__(self):
        return self.name


class Movie(Model):
    class Status(TextChoices):
        DRAFT = 'draft', 'Draft'
        PUBLISHED = 'published', 'Published'

    class Certificate(TextChoices):
        ALL = 'all', "Barcha yosh"
        SIX = '6+', '6+'
        TWELVE = '12+', '12+'
        SIXTEEN = '16+', '16+'
        EIGHTEEN = '18+', '18+'

    title = CharField(max_length=255)
    original_title = CharField(max_length=255, blank=True, null=True,
                               help_text="Asl nomi (masalan: Крёстный отец) — qidiruv uchun")
    slug = models.SlugField(max_length=255, unique=True, blank=True)
    description = TextField()
    release_date = DateField(db_index=True)
    duration_minutes = PositiveIntegerField(help_text="Davomiyligi (daqiqada)")
    poster = ImageField(upload_to='posters/', blank=True, null=True)
    banner = ImageField(
        upload_to='banners/', blank=True, null=True,
        help_text=(
            "Keng formatli banner (16:9, tavsiya 1920x1080) — bosh sahifa slayderi "
            "uchun; bo'sh qolsa poster ishlatiladi"
        ),
    )
    video_url = URLField(
        max_length=500, blank=True, null=True,
        help_text=(
            "YouTube treyler havolasi (faqat treyler ko'rsatiladi). "
            "Masalan: https://youtu.be/... yoki to'g'ridan-to'g'ri mp4"
        ),
    )
    certificate = CharField(max_length=10, choices=Certificate.choices, blank=True,
                            help_text="Yosh cheklovi (16+, 18+ ...)")
    language = CharField(max_length=100, blank=True, help_text="Asosiy til (masalan: Inglizcha)")
    country = CharField(max_length=100, blank=True, help_text="Mamlakat (masalan: AQSh)")
    studio = CharField(max_length=200, blank=True, help_text="Kino studiyasi")
    budget = PositiveBigIntegerField(null=True, blank=True, help_text="Byudjet (USD)")
    box_office = PositiveBigIntegerField(null=True, blank=True, help_text="Kassa yig'imi (USD)")
    genres = models.ManyToManyField(Genre, related_name='movies', blank=True)
    rating = DecimalField(max_digits=3, decimal_places=1, null=True, blank=True,
                          help_text="Foydalanuvchilar bahosining o'rtachasi (avtomatik)")
    rating_count = PositiveIntegerField(default=0, help_text="Baholar soni (avtomatik)")
    views_count = PositiveIntegerField(default=0)
    status = CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    search_text = TextField(blank=True, default='',
                            db_index=True,
                            help_text="Qidiruv uchun normalizatsiyalangan matn (avtomatik)")
    updated_at = DateTimeField(auto_now=True, help_text="Sitemap lastmod uchun (avtomatik)")

    class Meta:
        ordering = [F('rating').desc(nulls_last=True), F('views_count').desc()]

    def __str__(self):
        return self.title

    def _build_search_text(self):
        parts = [
            self.title or '', self.original_title or '',
            self.description or '', self.language or '',
            self.country or '', self.studio or '',
        ]
        normalized = list(parts) + [to_latin(p) for p in parts if p]
        return ' '.join(p.strip() for p in normalized if p and p.strip()).lower()

    def save(self, *args, **kwargs):
        make_poster = bool(self.poster) and _image_changed(self, 'poster')
        make_banner = bool(self.banner) and _image_changed(self, 'banner')
        if make_poster:
            smart_convert(self, 'poster', (600, 900))
        if make_banner:
            smart_convert(self, 'banner', (1920, 1080))
        self.search_text = self._build_search_text()
        super().save(*args, **kwargs)
        if make_poster:
            self._make_variants('poster')
        if make_banner:
            self._make_variants('banner')

    def _image_variant(self, field_name, ext):
        field = getattr(self, field_name)
        if not field:
            return None
        rel = str(Path(field.name).with_suffix('.' + ext))
        if _storage_has(field.storage, rel):
            return field.storage.url(rel)
        return None

    @property
    def poster_webp(self):
        return self._image_variant('poster', 'webp')

    @property
    def poster_avif(self):
        return self._image_variant('poster', 'avif')

    @property
    def banner_webp(self):
        return self._image_variant('banner', 'webp')

    @property
    def banner_avif(self):
        return self._image_variant('banner', 'avif')

    def _make_variants(self, field_name):
        from PIL import Image
        field = getattr(self, field_name)
        if not field:
            return
        try:
            src = Path(field.path)
        except NotImplementedError:
            return
        if src.suffix.lower() == '.svg':
            return
        try:
            img = Image.open(src).convert('RGB')
            for ext, fmt, quality in (('webp', 'WEBP', 82), ('avif', 'AVIF', 60)):
                out = src.with_suffix('.' + ext)
                if not out.exists():
                    img.save(out, fmt, quality=quality)
        except Exception as exc:
            logger.warning('Image variant yaratishda xato (%s): %s', field_name, exc)

    def get_absolute_url(self):
        return f'/film/{self.slug}/'

    def get_youtube_id(self):
        if not self.video_url:
            return None
        patterns = [
            r'youtu\.be/([a-zA-Z0-9_-]{11})',
            r'youtube\.com/watch\?v=([a-zA-Z0-9_-]{11})',
            r'youtube\.com/embed/([a-zA-Z0-9_-]{11})',
        ]
        for pattern in patterns:
            match = re.search(pattern, self.video_url)
            if match:
                return match.group(1)
        return None

    def is_youtube_trailer(self):
        return self.get_youtube_id() is not None

    # === IMDb UCHUN YANGI METODLAR ===

    def get_imdb_id(self):
        """IMDb havolasidan 'tt1234567' shaklidagi unikal ID-ni qirqib oladi."""
        if self.video_url:
            match = re.search(r'tt\d+', self.video_url)
            if match:
                id_value = match.group(0)
                if re.match(r'^tt\d{1,10}$', id_value):
                    return id_value
        return None

    def is_imdb_url(self):
        """Kiritilgan video_url IMDb havolasi ekanligini aniqlaydi."""
        return self.get_imdb_id() is not None

    def get_imdb_embed_url(self):
        """IMDb ID bo'yicha iframe ichida ijro etiladigan pleyer havolasini shakllantiradi."""
        imdb_id = self.get_imdb_id()
        if imdb_id and re.match(r'^tt\d{1,10}$', imdb_id):
            return f"https://vidsrc.to/embed/movie/{imdb_id}"
        return self.video_url


class Person(Model):
    full_name = CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True, blank=True)
    bio = TextField(blank=True, help_text="Qisqa biografiya")
    photo = ImageField(upload_to='people/', blank=True, null=True)
    birth_date = DateField(null=True, blank=True)
    birth_place = CharField(max_length=255, blank=True)
    updated_at = DateTimeField(auto_now=True, help_text="Sitemap lastmod uchun (avtomatik)")

    class Meta:
        verbose_name = "Aktyor / jamoa a'zosi"
        verbose_name_plural = "Aktyorlar va jamoa"
        ordering = ['full_name']

    def __str__(self):
        return self.full_name

    def save(self, *args, **kwargs):
        if self.photo and _image_changed(self, 'photo'):
            smart_convert(self, 'photo', (600, 800))
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return f'/person/{self.slug}/'


class Credit(Model):
    class Role(TextChoices):
        ACTOR = 'actor', 'Aktyor'
        DIRECTOR = 'director', 'Rejissyor'
        WRITER = 'writer', 'Ssenariy muallifi'
        PRODUCER = 'producer', 'Produser'
        COMPOSER = 'composer', 'Kompozitor'

    movie = models.ForeignKey(Movie, related_name='credits', on_delete=models.CASCADE)
    person = models.ForeignKey(Person, related_name='credits', on_delete=models.CASCADE)
    role = CharField(max_length=20, choices=Role.choices, default=Role.ACTOR)
    character_name = CharField(max_length=255, blank=True,
                               help_text="Aktyor o'ynagan qahramon nomi (faqat aktyorlar uchun)")

    class Meta:
        unique_together = ('movie', 'person', 'role')
        ordering = ['role', 'person__full_name']

    def __str__(self):
        label = self.character_name or self.get_role_display()
        return f"{self.person.full_name} — {label} ({self.movie.title})"


class MovieReview(Model):
    movie = models.ForeignKey(Movie, related_name='reviews', on_delete=models.CASCADE)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='reviews', on_delete=models.CASCADE)
    text = TextField(max_length=2000, help_text="Fikr-mulohazangiz")
    created_at = DateTimeField(auto_now_add=True)
    updated_at = DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('movie', 'user')
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.full_name} — {self.movie.title}"


class WatchlistItem(Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='watchlist', on_delete=models.CASCADE)
    movie = models.ForeignKey(Movie, related_name='watchlist_items', on_delete=models.CASCADE)
    created_at = DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'movie')
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.full_name} — {self.movie.title}"


class MovieRating(Model):
    class Meta:
        unique_together = ('movie', 'user')

    movie = models.ForeignKey(Movie, related_name='ratings', on_delete=models.CASCADE)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='ratings', on_delete=models.CASCADE)
    value = PositiveIntegerField(choices=[(i, str(i)) for i in range(1, 11)])
    created_at = DateTimeField(auto_now_add=True)
    updated_at = DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.full_name} → {self.movie.title}: {self.value}"


@receiver([post_save, post_delete], sender=MovieRating)
def recalculate_movie_rating(sender, instance, **kwargs):
    aggregate = MovieRating.objects.filter(movie_id=instance.movie_id).aggregate(
        avg=Avg('value'),
        cnt=Count('value'),
    )
    Movie.objects.filter(pk=instance.movie_id).update(
        rating=aggregate['avg'],
        rating_count=aggregate['cnt'],
    )
