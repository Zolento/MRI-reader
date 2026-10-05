# -*- mode: python ; coding: utf-8 -*-
block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[
        'src',
        'src.main',
        'src.main_window',
        'src.app',
        'src.app.file_loader',
        'src.app.display',
        'src.app.enhancement',
        'src.app.lazy',
        'src.core',
        'src.core.mri_data',
        'src.core.kspace_converter',
        'src.core.image_processor',
        'src.core.views',
        'src.ui',
        'src.ui.image_canvas',
        'src.ui.enhancement_panel',
        'src.ui.slice_navigator',
        'PyQt5',
        'PyQt5.QtCore',
        'PyQt5.QtGui',
        'PyQt5.QtWidgets',
        'numpy',
        'scipy',
        'scipy.fft',
        'scipy.ndimage',
        'h5py',
        'PIL',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='MRI-Reader',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # 设置为True可以显示调试窗口
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='MRI-Reader',
)
