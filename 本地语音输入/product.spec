from pathlib import Path
import PySide6
from PyInstaller.utils.hooks import collect_dynamic_libs, collect_submodules

root = Path(SPECPATH)
a = Analysis([str(root / 'src' / 'launcher.py')], pathex=[str(root / 'src')],
    binaries=collect_dynamic_libs('sherpa_onnx'), datas=[],
    hiddenimports=collect_submodules('pynput.keyboard') + collect_submodules('pynput.mouse'),
    hookspath=[], runtime_hooks=[],
    excludes=['tkinter', 'PySide6.QtWebEngineCore', 'PySide6.QtWebEngineWidgets', 'PIL', 'pytest'],
    noarchive=False)
# Qt 6.11 requires a newer MSVC runtime than the Python 3.11 wheel collector
# may select. Use Qt's bundled, backward-compatible runtime at the bundle root.
qt_dir = Path(PySide6.__file__).resolve().parent
runtime_dlls = [p for p in qt_dir.glob('*.dll') if p.name.lower().startswith(('vcruntime', 'msvcp'))]
runtime_names = {p.name.lower() for p in runtime_dlls}
a.binaries = [entry for entry in a.binaries if not ('/' not in entry[0] and '\\' not in entry[0] and entry[0].lower() in runtime_names)]
a.binaries += [(p.name, str(p), 'BINARY') for p in runtime_dlls]
# Qt uses the Windows ICU ABI; Poppler on the build PATH has a different ABI.
# Exclude those unrelated copies and let the Windows loader use its OS library.
a.binaries = [entry for entry in a.binaries if Path(entry[0]).name.lower() not in {'icuuc.dll', 'icudt78.dll'}]
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='本地语音输入',
    debug=False, strip=False, upx=False, console=False,
    icon=str(root / 'assets' / 'app-icon.ico'))
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='本地语音输入')
