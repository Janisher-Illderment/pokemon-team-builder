# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for poke-builder.
# Run: pyinstaller poke-builder.spec
# Output: dist/poke-builder.exe (Windows) or dist/poke-builder (Linux/macOS)

block_cipher = None

a = Analysis(
    ["pokemon_team_builder/cli/main.py"],
    pathex=[],
    binaries=[],
    datas=[
        ("pokemon_team_builder/data/legal_pool_mA.json", "pokemon_team_builder/data"),
        ("pokemon_team_builder/data/type_chart.json",    "pokemon_team_builder/data"),
        ("pokemon_team_builder/data/role_sp_templates.json", "pokemon_team_builder/data"),
    ],
    hiddenimports=[
        "hishel",
        "hishel._sync",
        "anyio",
        "anyio._backends._asyncio",
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
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="poke-builder",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
