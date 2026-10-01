"""Separate immutable product files from per-user writable state."""
import os
from pathlib import Path
import sys

APP_ROOT = Path(sys.executable).resolve().parent if getattr(sys, 'frozen', False) else Path(__file__).resolve().parent.parent
USER_DATA = Path(os.environ.get('LOCALAPPDATA', str(Path.home()))) / 'BubbleDictation'
VERSION = '1.0.2'


def user_file(name):
    USER_DATA.mkdir(parents=True, exist_ok=True)
    return USER_DATA / name
