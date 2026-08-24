# CINEMA — Django kino platformasi

Kino katalogi, baholash (1–10), leaderboard, sharhlar, "keyin ko'raman" ro'yxati, filmografiya, Top-meta ma'lumotlar va boshqalarni o'z ichiga olgan to'liq Django loyihasi.

## Texnologiyalar

- **Backend:** Python 3.11+, Django 5.2, django-unfold (admin), psycopg (PostgreSQL)
- **Frontend:** HTML, CSS (mujassam, dark), vanilla JS (AJAX baholash, video modal)
- **Infrastruktura:** SQLite (lokal) / PostgreSQL (prod), whitenoise (statik), python-dotenv, SEO (sitemap, robots.txt, Open Graph, JSON-LD Movie schema)
- **Xavfsizlik:** parol/register rate-limit, bot-traffic filtr, prod'da strict env tekshiruvi, HSTS
- **Media:** Cloudflare R2 / AWS S3 ga avtomoat (retsept bo'yicha) — posterlar deploy'da yo'qolmaydi

## Talablar va o'rnatish

```bash
# 1. Repozitoriyni klonlash
git clone <repo-url> cinema
cd cinema

# 2. Virtual muhit + paketlar (Windows)
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

# 3. Muhit fayli (ixtiyoriy — defaults ishlaydi)
copy .env.example .env

# 4. DB migratsiya + demo ma'lumotlar
python manage.py migrate
python manage.py seed_catalog        # 41 film, 86 shaxs, SVG posterlar, 290 baho

# 5. Superuser yaratish
python manage.py createsuperuser

# 6. Ishga tushirish
python manage.py runserver
# http://127.0.0.1:8000/
```

## Demo hisoblar

| Rol | Login (telefon) | Parol |
| --- | --- | --- |
| Superuser (ADMIN) | `997910309` | `admin123` |
| Demo foydalanuvchi 1 | `+998901000101` | `demo1234` |
| Demo foydalanuvchi 2 | `+998901000102` | `demo1234` |
| ... | `+998901000103` — `+998901000107` | `demo1234` |

> `seed_catalog` buyrug'i idempotent — bir necha marta ishga tushirish mumkin, dublikat yaratmaydi.

## Funksiyalar

- **Asosiy sahifa:** hero, qidiruv (nom/tavsif/janr/aktyor/til/mamlakat, kirill-lotin transliteratsiya), janr/yil/sort filtrlari, trend filmlar, paginatsiya, fragment cache
- **Kino sahifasi:** poster, metama'lumotlar (janr, sertifikat, til, mamlakat, studiya, byudjet/kassa), treyler modal (YouTube; 153-xato bo'lsa "YouTube'da ochish" tugmasi), JSON-LD Movie schema, baholash (1–10, AJAX), sharhlar, aktyorlar/jamoa, o'xshash filmlar, "Saqlash" (AJAX)
- **Liderboard:** eng yuqori baholangan filmlar reytingi (medal, ochko, paginatsiya)
- **Shaxs sahifasi:** biografiya, filmografiya (rollar bo'yicha), mashhur asarlar
- **Profil:** ma'lumotlarini tahrirlash, parolni almashtirish/tiklash, shaxsiy baholar, saqlangan ro'yxat
- **Admin:** film/shaxs/sharh/baho CRUD, inline-creditlar, avto reyting signali, KPI dashboard

## Telegram treyler/yuklama import (y vaziyatda kino fayli ham)

Kino sahifasida treyler (YouTube) o'ynatiladi — sayt IMDb kabi katalog. Agar kerak bo'lsa, to'g'ridan-to'g'ri mp4 (masalan Telegram fayl) ham `video_url` ga qo'yilishi mumkin:

1. Videoni botga yuboring: **@BreakingBad_BetterCallSaul_bot** (yoki bot admin bo'lgan kanalga post)
2. `python manage.py tg poll` — yuborilgan videolar ro'yxati chiqadi
3. Ko'rsatilgan `tg://<file_path>` qiymatini filmning **Video URL** maydoniga yozing — token brauzerga chiqmaydi (server tomondan proxy orqali oqimlanadi)

> Telegram botlar fayl yuklanmaydi 20 MB dan katta faylni; to'liq kino uchun YouTube (o'z kanal, Unlisted+embed) yoki hosting ishlating.

## Testlar

```bash
python manage.py test apps   # 60 ta test
```

## Deploy (Render)

```bash
python manage.py collectstatic --noinput
```

Bo'lsa, Render'da:

1. GitHub repo'ga push qiling
2. Render'da `render.yaml` asosida "New Blueprint" yaratish
3. Muhit: `DJANGO_SECRET_KEY`, `DJANGO_ALLOWED_HOSTS`, `DJANGO_DEBUG=False`, `DATABASE_URL` (avtomatik)
4. **Media** (posterlar/avatarlar) yo'qolmasligi uchun Cloudflare R2 (bepul) sozlang:
   - R2 da bucket + API token yarating; .env'ga:
   - `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_S3_ENDPOINT_URL` (https://<id>.r2.cloudflarestorage.com), `AWS_STORAGE_BUCKET_NAME`, `MEDIA_URL=https://pub-<id>.r2.dev/`
5. **Parol tiklash** ishlashi uchun SMTP (Brevo bepul): `DJANGO_EMAIL_HOST=smtp-relay.brevo.com`, `DJANGO_EMAIL_HOST_USER`, `DJANGO_EMAIL_HOST_PASSWORD`

> Prod'da `DJANGO_SECRET_KEY` yoki `DJANGO_ALLOWED_HOSTS` bo'lmasa — ilova ishga tushmaydi (xavfsizlik). Shu ataylab qilingan.

Yoki `Procfile` + gunicorn:
```bash
gunicorn IMDb.wsgi --bind 0.0.0.0:$PORT
```

## Loyiha tuzilishi

```
apps/
  models.py          # 7 model (Movie, Person, Credit, MovieRating, ...)
  views.py           # barcha sahifalar
  forms.py           # Ro'yxatdan o'tish, baholash, profil formalari
  admin.py           # django-unfold sozlamalari
  sitemaps.py        # search engine sitemap
  management/commands/seed_catalog.py  # demo ma'lumotlar
  templatetags/cinema_filters.py       # millions(), truncate ...
templates/           # barcha sahifalar (base.html + extends)
IMDb/settings.py     # env, whitenoise, security, database
```