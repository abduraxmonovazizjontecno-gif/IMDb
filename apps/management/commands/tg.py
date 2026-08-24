import json
import sys
import urllib.error
import urllib.parse
import urllib.request

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


def _api(token, method, params=None):
    url = 'https://api.telegram.org/bot' + token + '/' + method
    if params:
        url += '?' + urllib.parse.urlencode(params)
    try:
        with urllib.request.urlopen(url, timeout=60) as resp:
            data = json.load(resp)
    except urllib.error.HTTPError as exc:
        raise CommandError(f"Telegram {method}: HTTP {exc.code} {exc.reason}") from exc
    except (urllib.error.URLError, OSError, ValueError) as exc:
        raise CommandError(f"Telegram {method}: tarmoq xatosi ({exc})") from exc
    if not data.get('ok'):
        raise CommandError(f"Telegram {method}: {data.get('description', 'error')}")
    return data.get('result')


class Command(BaseCommand):
    help = (
        'Telegram video import: buning uchun avval filmni botga yuboring '
        '(@Film+Subtitr kanaliga yoki botga shaxsiy xabar), keyin: '
        'python manage.py tg poll'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            'action',
            nargs='?',
            default='poll',
            choices=['poll', 'link'],
        )
        parser.add_argument(
            'file_id',
            nargs='?',
            help='link uchun: Telegram file_id',
        )
        parser.add_argument(
            '--offset',
            type=int,
            default=0,
            help='getUpdates offset (0 = hamma oqimdan boshlab)',
        )

    def handle(self, *args, **options):
        if sys.stdout.encoding.lower().startswith('cp'):
            sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        token = settings.TELEGRAM_BOT_TOKEN
        if not token:
            raise CommandError('.env da TELEGRAM_BOT_TOKEN topilmadi')

        self.stdout.write('Botni tekshirish...')
        me = _api(token, 'getMe')
        self.stdout.write(f"Bot: @{me['username']}")

        if options['action'] == 'link':
            file_id = options['file_id']
            if not file_id:
                raise CommandError('file_id ko\'rsating: python manage.py tg link <file_id>')
            try:
                res = _api(token, 'getFile', {'file_id': file_id})
            except CommandError as exc:
                self.stdout.write(self.style.ERROR(str(exc)))
                self.stdout.write(self.style.WARNING(
                    'Bu file_id boshqa botdan olingan bo\'lishi mumkin '
                    '(faqat shu botdan olingan ID ishlaydi).'
                ))
                return
            self.stdout.write(f"  file_size: {res.get('file_size', 0) / 1048576:.1f} MB")
            self.stdout.write('  video_url ga xavfsiz (token yashirin) yozish uchun:')
            self.stdout.write(f"  tg://{res['file_path']}")
            self.stdout.write(f"  file_path: {res['file_path']}")
            return

        self.stdout.write('Yangi xabarlarni o\'qish...')
        updates = _api(token, 'getUpdates', {'offset': options['offset']})
        found = 0
        for upd in updates:
            msg = upd.get('message') or upd.get('channel_post') or {}
            media = msg.get('video') or msg.get('document') or msg.get('audio') or msg.get('animation')
            if not media:
                continue
            found += 1
            caption = (msg.get('caption') or '').splitlines()[0]
            fpath = self._file_path(token, media['file_id'])
            self.stdout.write('')
            self.stdout.write(f"--- #{found} ---")
            self.stdout.write(f"  caption : {caption}")
            self.stdout.write(f"  mime    : {media.get('mime_type')}")
            self.stdout.write(f"  size    : {media.get('file_size', 0) / 1048576:.1f} MB")
            self.stdout.write(f"  file_id : {media['file_id']}")
            self.stdout.write("  video_url ga xavfsiz (token yashirin) yozish uchun:")
            self.stdout.write(f"  tg://{fpath}")
            self.stdout.write(f"  file_path : {fpath}")
        if not found:
            self.stdout.write(self.style.WARNING(
                'Video topilmadi. Video faylni botga yuboring '
                f"(@{me['username']}) yoki bot admin bo\u2019lgan kanalga post qiling, "
                'keyin buyruqni yana bajaring.'
            ))

    @staticmethod
    def _file_path(token, file_id):
        res = _api(token, 'getFile', {'file_id': file_id})
        return res['file_path']
