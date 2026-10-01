"""Offline release checks: no HTTP listener, accounts, uploads or publishing."""
import ast
import hashlib
import importlib.metadata
import json
from pathlib import Path
import sys
import tempfile

root = Path(sys.argv[1]).resolve()
program = root / '程序文件'
checks = {}
blocked = ('cookiesFile', 'videoFile', 'db', 'logs', 'avatars', '.starter')
checks['user_data_empty'] = all(not any((program / name).rglob('*')) for name in blocked)
checks['default_config'] = (program / 'conf.py').read_bytes() == (program / 'conf.example.py').read_bytes()
checks['launcher_present'] = (root / '自媒体一键分发.exe').read_bytes()[:2] == b'MZ'
checks['frontend_present'] = (program / 'frontend/dist/index.html').is_file()
checks['backend_parses'] = bool(ast.parse((program / 'main.py').read_text(encoding='utf-8-sig')))
sys.path.insert(0, str(program))
import conf
temporary_data = tempfile.TemporaryDirectory(prefix='toolbox-publisher-check-')
conf.BASE_DIR = Path(temporary_data.name)
import main
response = main.app.test_client().get('/')
checks['frontend_route'] = response.status_code == 200 and b'<html' in response.data.lower()
from playwright.sync_api import sync_playwright
with sync_playwright() as playwright:
    checks['bundled_browser_present'] = Path(playwright.chromium.executable_path).is_file()
    browser = playwright.chromium.launch(headless=True)
    page = browser.new_page()
    page.set_content('<title>Toolbox offline test</title><main>OK</main>')
    checks['bundled_browser_offline'] = page.title() == 'Toolbox offline test'
    browser.close()
checks['user_data_still_empty'] = all(not any((program / name).rglob('*')) for name in blocked)
versions = {name: importlib.metadata.version(name) for name in ('flask', 'flask-cors', 'playwright', 'xhs', 'biliup', 'loguru', 'qrcode', 'requests')}
print(json.dumps({'passed':all(checks.values()), 'checks':checks, 'dependencies':versions}, ensure_ascii=False, indent=2))
from loguru import logger
logger.remove()
temporary_data.cleanup()
raise SystemExit(0 if all(checks.values()) else 1)
