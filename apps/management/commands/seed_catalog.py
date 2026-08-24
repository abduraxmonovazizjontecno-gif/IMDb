from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils.text import slugify

from apps.models import Credit, Genre, Movie, MovieRating, Person, User


def _wrap(text, max_chars=20):
    words, lines, cur = text.split(), [], ''
    for w in words:
        if cur and len(cur) + len(w) + 1 > max_chars:
            lines.append(cur)
            cur = w
        else:
            cur = f'{cur} {w}'.strip()
    if cur:
        lines.append(cur)
    return lines


def make_poster(path, title, year):
    import html as html_mod
    title = html_mod.escape(title)
    lines = _wrap(title)
    dy = 430 - (len(lines) - 1) * 26
    tspans = ''.join(
        f'<tspan x="300" y="{dy + i * 52}">{line}</tspan>'
        for i, line in enumerate(lines)
    )
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="600" height="900" viewBox="0 0 600 900">
<defs>
<linearGradient id="g" x1="0" y1="0" x2="1" y2="1">
<stop offset="0" stop-color="#1c1d22"/><stop offset="1" stop-color="#0a0b0d"/>
</linearGradient>
<linearGradient id="gold" x1="0" y1="0" x2="1" y2="0">
<stop offset="0" stop-color="#ffe2a1"/><stop offset="1" stop-color="#d9a63c"/>
</linearGradient>
</defs>
<rect width="600" height="900" fill="url(#g)"/>
<rect x="26" y="26" width="548" height="848" fill="none" stroke="#f0c45a" stroke-opacity="0.45" stroke-width="2"/>
<rect x="38" y="38" width="524" height="824" fill="none" stroke="#f0c45a" stroke-opacity="0.14" stroke-width="1"/>
<text font-family="Georgia, serif" font-size="46" fill="url(#gold)" text-anchor="middle" font-weight="bold">{tspans}</text>
<text x="300" y="690" font-family="Arial, sans-serif" font-size="26" fill="#878b93" text-anchor="middle" letter-spacing="4">{year}</text>
<text x="300" y="750" font-family="Arial, sans-serif" font-size="15" fill="#f0c45a" text-anchor="middle" letter-spacing="8">CINEMA</text>
</svg>'''
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(svg, encoding='utf-8')


GENRES = [
    ('drama', 'Drama'), ('crime', 'Kriminal'), ('thriller', 'Triller'),
    ('sci-fi', 'Ilmiy fantastika'), ('action', 'Jangari'), ('adventure', 'Sarguzasht'),
    ('romance', 'Romantik'), ('war', 'Urush'), ('fantasy', 'Fantastika'),
    ('animation', 'Animatsiya'), ('mystery', 'Detektiv'), ('comedy', 'Komediya'),
    ('horror', 'Qo\'rqinchli'), ('western', 'Vestern'), ('documentary', 'Dokumental'),
]

# (title, year, duration, certificate, [genres], director, [actors], country, studio, budget_M, box_M, rating_bias, description)
MOVIES = [
    ('The Godfather', 1972, 175, '16+', ['drama', 'crime'], 'Francis Ford Coppola', ['Marlon Brando', 'Al Pacino'], 'AQSh', 'Paramount Pictures', 6, 250, 9.2, 'Korleone oilasi — eng buyuk mafiya dramasi.'),
    ('The Godfather Part II', 1974, 202, '16+', ['drama', 'crime'], 'Francis Ford Coppola', ['Al Pacino', 'Robert De Niro'], 'AQSh', 'Paramount Pictures', 13, 93, 9.0, 'Maykl Korleone hokimiyatni mustahkamlaydi.'),
    ('Schindler\'s List', 1993, 195, '16+', ['drama', 'war'], 'Steven Spielberg', ['Liam Neeson', 'Ralph Fiennes'], 'AQSh', 'Universal Pictures', 22, 322, 8.9, 'Oskar Shindler yuzlab yahudiy hayotini qutqaradi.'),
    ('Pulp Fiction', 1994, 154, '18+', ['crime', 'drama'], 'Quentin Tarantino', ['John Travolta', 'Samuel L. Jackson'], 'AQSh', 'Miramax', 8, 214, 8.8, 'Los-Anjeles jinoyat olamining epizodik hikoyalari.'),
    ('Fight Club', 1999, 139, '18+', ['drama', 'thriller'], 'David Fincher', ['Brad Pitt', 'Edward Norton'], 'AQSh', '20th Century Fox', 63, 101, 8.8, 'Uyqusiz xodim va g\'alati sabunsoz...'),
    ('Forrest Gump', 1994, 142, '12+', ['drama', 'romance'], 'Robert Zemeckis', ['Tom Hanks', 'Robin Wright'], 'AQSh', 'Paramount Pictures', 55, 678, 8.8, 'Oddiy qalbli Forrestning hayot sarguzashtlari.'),
    ('The Matrix', 1999, 136, '16+', ['sci-fi', 'action'], 'The Wachowskis', ['Keanu Reeves', 'Laurence Fishburne'], 'AQSh', 'Warner Bros.', 63, 467, 8.7, 'Neo haqiqat zindonidan chiqish yo\'lini topadi.'),
    ('Goodfellas', 1990, 146, '18+', ['crime', 'drama'], 'Martin Scorsese', ['Ray Liotta', 'Robert De Niro'], 'AQSh', 'Warner Bros.', 25, 47, 8.7, 'Genri Hillning mafiya hayotidagi yuksalish va qulashi.'),
    ('Se7en', 1995, 127, '18+', ['crime', 'thriller'], 'David Fincher', ['Brad Pitt', 'Morgan Freeman'], 'AQSh', 'New Line Cinema', 33, 327, 8.6, 'Yetti gunoh asosida qotilliklar sodir etuvchi jinoyatchi.'),
    ('The Silence of the Lambs', 1991, 118, '18+', ['thriller', 'crime'], 'Jonathan Demme', ['Jodie Foster', 'Anthony Hopkins'], 'AQSh', 'Orion Pictures', 19, 273, 8.6, 'Yosh agent Hannibal Lektrdan yordam so\'raydi.'),
    ('The Shawshank Redemption', 1994, 142, '16+', ['drama', 'crime'], 'Frank Darabont', ['Tim Robbins', 'Morgan Freeman'], 'AQSh', 'Castle Rock', 25, 73, 9.3, 'Zindondagi umid va do\'stlik haqidagi abadiy hikoya.'),
    ('The Departed', 2006, 151, '18+', ['crime', 'thriller'], 'Martin Scorsese', ['Leonardo DiCaprio', 'Matt Damon'], 'AQSh', 'Warner Bros.', 90, 291, 8.5, 'Mafiya va politsiya bir-biriga maxfiy odam yuboradi.'),
    ('Gladiator', 2000, 155, '16+', ['action', 'adventure'], 'Ridley Scott', ['Russell Crowe', 'Joaquin Phoenix'], 'AQSh', 'DreamWorks', 103, 460, 8.5, 'Imperatorga qasos olgan general Maksimus.'),
    ('Saving Private Ryan', 1998, 169, '16+', ['war', 'drama'], 'Steven Spielberg', ['Tom Hanks', 'Matt Damon'], 'AQSh', 'DreamWorks', 70, 482, 8.6, 'Normandiya jangidan so\'ng askarni topish missiyasi.'),
    ('The Green Mile', 1999, 189, '16+', ['drama'], 'Frank Darabont', ['Tom Hanks', 'Michael Clarke Duncan'], 'AQSh', 'Castle Rock', 60, 287, 8.6, 'Mo\'jiza kuchiga ega mahkum Pol Edjkomb.'),
    ('The Dark Knight', 2008, 152, '16+', ['action', 'crime', 'thriller'], 'Christopher Nolan', ['Christian Bale', 'Heath Ledger'], 'AQSh', 'Warner Bros.', 185, 1006, 9.0, 'Betmen Joker bilan yuzma-yuz.'),
    ('Interstellar', 2014, 169, '12+', ['drama', 'sci-fi', 'adventure'], 'Christopher Nolan', ['Matthew McConaughey', 'Anne Hathaway'], 'AQSh', 'Warner Bros.', 165, 715, 8.7, 'Insoniyat uchun yangi uy izlash — koinot sayohati.'),
    ('Inception', 2010, 148, '12+', ['sci-fi', 'action', 'drama'], 'Christopher Nolan', ['Leonardo DiCaprio', 'Joseph Gordon-Levitt'], 'AQSh', 'Warner Bros.', 160, 836, 8.8, 'Tushlar ichidagi o\'g\'rilik operatsiyasi.'),
    ('The Lord of the Rings: The Fellowship of the Ring', 2001, 178, '12+', ['fantasy', 'adventure'], 'Peter Jackson', ['Elijah Wood', 'Ian McKellen'], 'Yangi Zelandiya', 'New Line Cinema', 93, 897, 8.9, 'Uzuk birodarligi Mordorga yo\'l oladi.'),
    ('The Lord of the Rings: The Return of the King', 2003, 201, '12+', ['fantasy', 'adventure'], 'Peter Jackson', ['Elijah Wood', 'Ian McKellen'], 'Yangi Zelandiya', 'New Line Cinema', 94, 1142, 9.0, 'O\'rta Yer uchun so\'nggi jang.'),
    ('The Empire Strikes Back', 1980, 124, '12+', ['sci-fi', 'action'], 'Irvin Kershner', ['Mark Hamill', 'Harrison Ford'], 'AQSh', 'Lucasfilm', 32, 547, 8.7, 'Imperiya qarshi hujumga o\'tadi.'),
    ('Star Wars: A New Hope', 1977, 121, '12+', ['sci-fi', 'action'], 'George Lucas', ['Mark Hamill', 'Harrison Ford'], 'AQSh', 'Lucasfilm', 11, 775, 8.6, 'Galaktik imperiyaga qarshi qo\'zg\'olon.'),
    ('Titanic', 1997, 195, '12+', ['romance', 'drama'], 'James Cameron', ['Leonardo DiCaprio', 'Kate Winslet'], 'AQSh', 'Paramount Pictures', 200, 2264, 7.9, 'Kemada tug\'ilgan abadiy sevgi hikoyasi.'),
    ('Jaws', 1975, 124, '12+', ['thriller', 'adventure'], 'Steven Spielberg', ['Roy Scheider', 'Robert Shaw'], 'AQSh', 'Universal Pictures', 9, 476, 8.1, 'Odamxo\'r akula kurort shaharchasini vahima soladi.'),
    ('Aliens', 1986, 137, '16+', ['sci-fi', 'action'], 'James Cameron', ['Sigourney Weaver', 'Michael Biehn'], 'AQSh', '20th Century Fox', 18, 183, 8.4, 'Ripley koloniya sayyorasiga qaytadi.'),
    ('Terminator 2: Judgment Day', 1991, 137, '16+', ['sci-fi', 'action'], 'James Cameron', ['Arnold Schwarzenegger', 'Linda Hamilton'], 'AQSh', 'Carolco', 102, 520, 8.6, 'Terminator endi himoya qilish uchun keladi.'),
    ('The Lion King', 1994, 88, 'all', ['animation', 'adventure'], 'Roger Allers', ['James Earl Jones', 'Jeremy Irons'], 'AQSh', 'Walt Disney Pictures', 45, 968, 8.5, 'Arslon shahzoda Simbaning hikoyasi.'),
    ('Spirited Away', 2001, 125, 'all', ['animation', 'fantasy'], 'Hayao Miyazaki', ['Rumi Hiiragi', 'Miyu Irino'], 'Yaponiya', 'Studio Ghibli', 19, 395, 8.6, 'Qiz ruhlar olamiga tushib qoladi.'),
    ('Parasite', 2019, 132, '16+', ['thriller', 'drama'], 'Bong Joon-ho', ['Song Kang-ho', 'Cho Yeo-jeong'], 'Koreya Respublikasi', 'CJ Entertainment', 11, 266, 8.5, 'Ikki oilaning sinfiy kesishuvi.'),
    ('Joker', 2019, 122, '18+', ['crime', 'thriller'], 'Todd Phillips', ['Joaquin Phoenix'], 'AQSh', 'Warner Bros.', 55, 1074, 8.4, 'Artur Flekning Jokerga aylanishi.'),
    ('Whiplash', 2014, 106, '16+', ['drama'], 'Damien Chazelle', ['Miles Teller', 'J.K. Simmons'], 'AQSh', 'Sony Pictures Classics', 3, 49, 8.5, 'Yosh barabanchi va shafqatsiz ustoz.'),
    ('The Prestige', 2006, 130, '12+', ['mystery', 'drama'], 'Christopher Nolan', ['Hugh Jackman', 'Christian Bale'], 'AQSh', 'Warner Bros.', 40, 109, 8.5, 'Ikki sehrgarning halokatli raqobati.'),
    ('Memento', 2000, 113, '16+', ['thriller', 'mystery'], 'Christopher Nolan', ['Guy Pearce', 'Carrie-Anne Moss'], 'AQSh', 'Newmarket Films', 9, 40, 8.4, 'Qisqa muddatli xotirali odam qotilni qidiradi.'),
    ('Blade Runner 2049', 2017, 164, '16+', ['sci-fi', 'thriller'], 'Denis Villeneuve', ['Ryan Gosling', 'Harrison Ford'], 'AQSh', 'Warner Bros.', 155, 259, 8.0, 'Yangi replikant o\'z o\'tmishini topadi.'),
    ('Dune', 2021, 155, '12+', ['sci-fi', 'adventure'], 'Denis Villeneuve', ['Timothée Chalamet', 'Zendaya'], 'AQSh', 'Warner Bros.', 165, 402, 8.0, 'Arakis sayyorasi uchun kurash.'),
    ('Mad Max: Fury Road', 2015, 120, '16+', ['action', 'sci-fi'], 'George Miller', ['Tom Hardy', 'Charlize Theron'], 'Avstraliya', 'Warner Bros.', 150, 379, 8.1, 'Chol olamda ozodlikka qochish.'),
    ('Prisoners', 2013, 153, '16+', ['thriller', 'crime'], 'Denis Villeneuve', ['Hugh Jackman', 'Jake Gyllenhaal'], 'AQSh', 'Warner Bros.', 46, 122, 8.1, 'Qizi g\'oyib bo\'lgan ota qasos oladi.'),
    ('Arrival', 2016, 116, '12+', ['sci-fi', 'drama'], 'Denis Villeneuve', ['Amy Adams', 'Jeremy Renner'], 'AQSh', 'Paramount Pictures', 47, 203, 7.9, 'Tilshunos olim begona sivilizatsiya bilan muloqot qiladi.'),
    ('The Truman Show', 1998, 103, '12+', ['drama', 'comedy'], 'Peter Weir', ['Jim Carrey', 'Laura Linney'], 'AQSh', 'Paramount Pictures', 60, 264, 8.2, 'Uning butun hayoti — jonli teleko\'rsatuv.'),
    ('Good Will Hunting', 1997, 126, '16+', ['drama'], 'Gus Van Sant', ['Matt Damon', 'Robin Williams'], 'AQSh', 'Miramax', 10, 225, 8.3, 'Daho farrosh o\'z iqtidorini kashf etadi.'),
    ('Heat', 1995, 170, '16+', ['crime', 'action'], 'Michael Mann', ['Al Pacino', 'Robert De Niro'], 'AQSh', 'Warner Bros.', 60, 187, 8.3, 'Mashhur o\'g\'ri va politsiyachining ta\'qibi.'),
]

PERSONS = {
    'Francis Ford Coppola': ('Francis Ford Coppola', 'francis-ford-coppola'),
    'Steven Spielberg': ('Steven Spielberg', 'steven-spielberg'),
    'Quentin Tarantino': ('Quentin Tarantino', 'quentin-tarantino'),
    'David Fincher': ('David Fincher', 'david-fincher'),
    'Robert Zemeckis': ('Robert Zemeckis', 'robert-zemeckis'),
    'The Wachowskis': ('The Wachowskis', 'the-wachowskis'),
    'Martin Scorsese': ('Martin Scorsese', 'martin-scorsese'),
    'Jonathan Demme': ('Jonathan Demme', 'jonathan-demme'),
    'Frank Darabont': ('Frank Darabont', 'frank-darabont'),
    'Ridley Scott': ('Ridley Scott', 'ridley-scott'),
    'Peter Jackson': ('Peter Jackson', 'peter-jackson'),
    'Irvin Kershner': ('Irvin Kershner', 'irvin-kershner'),
    'George Lucas': ('George Lucas', 'george-lucas'),
    'James Cameron': ('James Cameron', 'james-cameron'),
    'Roger Allers': ('Roger Allers', 'roger-allers'),
    'Hayao Miyazaki': ('Hayao Miyazaki', 'hayao-miyazaki'),
    'Bong Joon-ho': ('Bong Joon-ho', 'bong-joon-ho'),
    'Todd Phillips': ('Todd Phillips', 'todd-phillips'),
    'Damien Chazelle': ('Damien Chazelle', 'damien-chazelle'),
    'Denis Villeneuve': ('Denis Villeneuve', 'denis-villeneuve'),
    'George Miller': ('George Miller', 'george-miller'),
    'Peter Weir': ('Peter Weir', 'peter-weir'),
    'Gus Van Sant': ('Gus Van Sant', 'gus-van-sant'),
    'Michael Mann': ('Michael Mann', 'michael-mann'),
    'Marlon Brando': ('Marlon Brando', 'marlon-brando'),
    'Al Pacino': ('Al Pacino', 'al-pacino'),
    'Robert De Niro': ('Robert De Niro', 'robert-de-niro'),
    'Liam Neeson': ('Liam Neeson', 'liam-neeson'),
    'Ralph Fiennes': ('Ralph Fiennes', 'ralph-fiennes'),
    'John Travolta': ('John Travolta', 'john-travolta'),
    'Samuel L. Jackson': ('Samuel L. Jackson', 'samuel-l-jackson'),
    'Brad Pitt': ('Brad Pitt', 'brad-pitt'),
    'Edward Norton': ('Edward Norton', 'edward-norton'),
    'Tom Hanks': ('Tom Hanks', 'tom-hanks'),
    'Robin Wright': ('Robin Wright', 'robin-wright'),
    'Keanu Reeves': ('Keanu Reeves', 'keanu-reeves'),
    'Laurence Fishburne': ('Laurence Fishburne', 'laurence-fishburne'),
    'Ray Liotta': ('Ray Liotta', 'ray-liotta'),
    'Morgan Freeman': ('Morgan Freeman', 'morgan-freeman'),
    'Jodie Foster': ('Jodie Foster', 'jodie-foster'),
    'Anthony Hopkins': ('Anthony Hopkins', 'anthony-hopkins'),
    'Tim Robbins': ('Tim Robbins', 'tim-robbins'),
    'Leonardo DiCaprio': ('Leonardo DiCaprio', 'leonardo-dicaprio'),
    'Matt Damon': ('Matt Damon', 'matt-damon'),
    'Russell Crowe': ('Russell Crowe', 'russell-crowe'),
    'Joaquin Phoenix': ('Joaquin Phoenix', 'joaquin-phoenix'),
    'Michael Clarke Duncan': ('Michael Clarke Duncan', 'michael-clarke-duncan'),
    'Mark Hamill': ('Mark Hamill', 'mark-hamill'),
    'Harrison Ford': ('Harrison Ford', 'harrison-ford'),
    'Kate Winslet': ('Kate Winslet', 'kate-winslet'),
    'Roy Scheider': ('Roy Scheider', 'roy-scheider'),
    'Robert Shaw': ('Robert Shaw', 'robert-shaw'),
    'Sigourney Weaver': ('Sigourney Weaver', 'sigourney-weaver'),
    'Michael Biehn': ('Michael Biehn', 'michael-biehn'),
    'Arnold Schwarzenegger': ('Arnold Schwarzenegger', 'arnold-schwarzenegger'),
    'Linda Hamilton': ('Linda Hamilton', 'linda-hamilton'),
    'James Earl Jones': ('James Earl Jones', 'james-earl-jones'),
    'Jeremy Irons': ('Jeremy Irons', 'jeremy-irons'),
    'Rumi Hiiragi': ('Rumi Hiiragi', 'rumi-hiiragi'),
    'Miyu Irino': ('Miyu Irino', 'miyu-irino'),
    'Song Kang-ho': ('Song Kang-ho', 'song-kang-ho'),
    'Cho Yeo-jeong': ('Cho Yeo-jeong', 'cho-yeo-jeong'),
    'Miles Teller': ('Miles Teller', 'miles-teller'),
    'J.K. Simmons': ('J.K. Simmons', 'j-k-simmons'),
    'Hugh Jackman': ('Hugh Jackman', 'hugh-jackman'),
    'Guy Pearce': ('Guy Pearce', 'guy-pearce'),
    'Carrie-Anne Moss': ('Carrie-Anne Moss', 'carrie-anne-moss'),
    'Ryan Gosling': ('Ryan Gosling', 'ryan-gosling'),
    'Timothée Chalamet': ('Timothée Chalamet', 'timothee-chalamet'),
    'Zendaya': ('Zendaya', 'zendaya'),
    'Tom Hardy': ('Tom Hardy', 'tom-hardy'),
    'Charlize Theron': ('Charlize Theron', 'charlize-theron'),
    'Jake Gyllenhaal': ('Jake Gyllenhaal', 'jake-gyllenhaal'),
    'Amy Adams': ('Amy Adams', 'amy-adams'),
    'Jeremy Renner': ('Jeremy Renner', 'jeremy-renner'),
    'Jim Carrey': ('Jim Carrey', 'jim-carrey'),
    'Laura Linney': ('Laura Linney', 'laura-linney'),
    'Robin Williams': ('Robin Williams', 'robin-williams'),
    'Elijah Wood': ('Elijah Wood', 'elijah-wood'),
    'Ian McKellen': ('Ian McKellen', 'ian-mckellen'),
    'Christian Bale': ('Christian Bale', 'christian-bale'),
    'Heath Ledger': ('Heath Ledger', 'heath-ledger'),
    'Matthew McConaughey': ('Matthew McConaughey', 'matthew-mcconaughey'),
    'Anne Hathaway': ('Anne Hathaway', 'anne-hathaway'),
    'Joseph Gordon-Levitt': ('Joseph Gordon-Levitt', 'joseph-gordon-levitt'),
    'Christopher Nolan': ('Christopher Nolan', 'chris-nolan'),
}

DEMO_USERS = [
    ('+998901000101', 'Bekzod'), ('+998901000102', 'Malika'), ('+998901000103', 'Jasur'),
    ('+998901000104', 'Nilufar'), ('+998901000105', 'Sardor'), ('+998901000106', 'Gulnoza'),
    ('+998901000107', 'Timur'),
]
DEMO_PASSWORD = 'demo1234'


class Command(BaseCommand):
    help = 'Demo katalog: filmlar, aktyorlar/jamoa, SVG posterlar va baholar yaratadi (idempotent).'

    @transaction.atomic
    def handle(self, *args, **options):
        media = Path(settings.MEDIA_ROOT) / 'posters'
        genres = {slug: Genre.objects.get_or_create(slug=slug, defaults={'name': name})[0]
                  for slug, name in GENRES}

        persons = {}
        for name, (full, slug) in PERSONS.items():
            persons[name] = Person.objects.get_or_create(slug=slug, defaults={'full_name': full})[0]

        users = []
        for ph, name in DEMO_USERS:
            user, _ = User.objects.get_or_create(phone_number=ph, defaults={'full_name': name})
            if not user.password or not user.has_usable_password():
                user.set_password(DEMO_PASSWORD)
                user.save()
            users.append(user)

        made_movies = 0
        for (title, year, dur, cert, gslugs, director, actors, country, studio,
             budget_m, box_m, bias, desc) in MOVIES:
            slug = slugify(title)
            movie, created = Movie.objects.update_or_create(
                slug=slug,
                defaults=dict(
                    title=title, description=desc, release_date=f'{year}-06-01',
                    duration_minutes=dur, certificate=cert, language='Inglizcha',
                    country=country, studio=studio, budget=int(budget_m * 1e6),
                    box_office=int(box_m * 1e6), status='published',
                    views_count=bias * 1700 + (year % 5) * 940,
                ),
            )
            movie.genres.set(genres[s] for s in gslugs)
            if created:
                made_movies += 1
            make_poster(media / f'{slug}.svg', title, year)
            movie.poster = f'posters/{slug}.svg'
            movie.save(update_fields=['poster', 'search_text'])

            Credit.objects.get_or_create(movie=movie, person=persons[director], role='director')
            for actor in actors:
                Credit.objects.get_or_create(movie=movie, person=persons[actor], role='actor')

            for i, user in enumerate(users):
                delta = [0, 0.3, -0.2, 0.5, -0.4, 0.1, -0.6][i % 7]
                value = min(10, max(5, round(bias + delta)))
                MovieRating.objects.update_or_create(
                    movie=movie, user=user, defaults={'value': value},
                )

        self.stdout.write(self.style.SUCCESS(
            f'Tayyor: {len(MOVIES)} film ({made_movies} yangi), '
            f'{len(persons)} shaxs, {len(users)} foydalanuvchi, posterlar {media} da.'))
