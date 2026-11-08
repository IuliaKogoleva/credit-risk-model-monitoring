"""
Скриншот дашборда для превью ссылки (og:image): LinkedIn, Telegram, Slack.

Открывает docs/index.html в режиме ?preview=1 (компактная вёрстка, английский язык,
светлая тема) и сохраняет docs/preview.png размером 1200×627 — формат, который
LinkedIn показывает без обрезки.

Запуск:
  pip install playwright && python -m playwright install chromium
  python src/preview.py            # по умолчанию папка docs
  python src/preview.py path/to/docs
"""
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

WIDTH, HEIGHT = 1200, 627


def make_preview(out_dir):
    out = Path(out_dir)
    page_path = (out / 'index.html').resolve()
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={'width': WIDTH, 'height': HEIGHT}, device_scale_factor=1, color_scheme='light')
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)))
        page.goto(page_path.as_uri() + '?preview=1&lang=en', wait_until='networkidle')
        page.wait_for_function('window.__dashboardReady === true', timeout=30_000)
        page.wait_for_timeout(500)
        if errors:
            raise RuntimeError('Ошибки JavaScript на странице: ' + '; '.join(errors))
        page.screenshot(path=str(out / 'preview.png'))
        browser.close()
    print('Превью:', out / 'preview.png')


if __name__ == '__main__':
    make_preview(sys.argv[1] if len(sys.argv) > 1 else Path(__file__).resolve().parents[1] / 'docs')
