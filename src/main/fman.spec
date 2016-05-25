# -*- mode: python -*-

a = Analysis(['python/fman/main.py'],
	datas=[('resources/*.*', '.')],
	hiddenimports=['osxtrash.impl']
)
pyz = PYZ(a.pure, a.zipped_data)
exe = EXE(pyz,
	a.scripts,
	exclude_binaries=True,
	name='fman',
	debug=False,
	strip=False,
	upx=True,
	console=False
)
coll = COLLECT(exe,
	a.binaries,
	a.zipfiles,
	a.datas,
	strip=False,
	upx=True,
	name='fman'
)
app = BUNDLE(coll,
	name='fman.app',
	icon=None,
	bundle_identifier=None
)