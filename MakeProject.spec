# -*- mode: python ; coding: utf-8 -*-

import re
from pathlib import Path

from PyInstaller.utils.hooks import get_package_paths

version_text = (Path("makeproject") / "__init__.py").read_text(encoding="utf-8")
match = re.search(r'__version__\s*=\s*["\']([^"\']+)["\']', version_text)
app_version = match.group(1) if match else "0.0.0"


_, pyqt6_path = get_package_paths("PyQt6")
qt_plugins = []
for plugin_group in ("platforms", "imageformats", "iconengines"):
    plugin_dir = Path(pyqt6_path) / "Qt6" / "plugins" / plugin_group
    if plugin_dir.exists():
        for plugin in plugin_dir.glob("*.dylib"):
            qt_plugins.append((str(plugin), f"PyQt6/Qt6/plugins/{plugin_group}"))

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=qt_plugins,
    datas=[
        ('makeproject/styles_base.qss', 'makeproject'),
        ('makeproject/styles_dark.qss', 'makeproject'),
        ('makeproject/styles_light.qss', 'makeproject'),
    ],
    hiddenimports=["pkgutil"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='MakeProject',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['assets/icon.icns'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='MakeProject',
)
app = BUNDLE(
    coll,
    name='MakeProject.app',
    icon='assets/icon.icns',
    bundle_identifier=None,
    info_plist={
        "CFBundleShortVersionString": app_version,
        "CFBundleVersion": app_version,
    },
)
