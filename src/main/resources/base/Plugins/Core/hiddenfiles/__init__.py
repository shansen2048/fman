from fman import platform
from os.path import basename, abspath

import ctypes

def is_hidden(path):
	if platform() == 'Mac':
		import hiddenfiles.mac
		return hiddenfiles.mac.is_hidden(path)
	elif platform() == 'Windows':
		attrs = ctypes.windll.kernel32.GetFileAttributesW(path)
		if attrs == -1:
			raise OSError('Could not obtain attributes for %r.' % path)
		return bool(attrs & 2)
	else:
		return basename(abspath(path)).startswith('.')