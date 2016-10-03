# Copied from http://pastebin.com/aCUwTumB

import contextlib
import ctypes

cf = ctypes.cdll.LoadLibrary(
	'/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation')

cf.CFShow.argtypes = [ctypes.c_void_p]
cf.CFShow.restype = None

cf.CFRelease.argtypes = [ctypes.c_void_p]
cf.CFRelease.restype = None

cf.CFStringCreateWithBytes.argtypes = [ctypes.c_void_p,
									   ctypes.c_char_p, ctypes.c_long,
									   ctypes.c_int, ctypes.c_int]
cf.CFStringCreateWithBytes.restype = ctypes.c_void_p

cf.CFStringGetMaximumSizeOfFileSystemRepresentation.argtypes = [ctypes.c_void_p]
cf.CFStringGetMaximumSizeOfFileSystemRepresentation.restype = ctypes.c_int

cf.CFStringGetFileSystemRepresentation.argtypes = [ctypes.c_void_p,
												   ctypes.c_char_p,
												   ctypes.c_long]
cf.CFStringGetFileSystemRepresentation.restype = ctypes.c_int

cf.CFURLCreateFromFileSystemRepresentation.argtypes = [ctypes.c_void_p,
													   ctypes.c_char_p,
													   ctypes.c_long,
													   ctypes.c_int]
cf.CFURLCreateFromFileSystemRepresentation.restype = ctypes.c_void_p

cf.CFURLCopyResourcePropertyForKey.argtypes = [ctypes.c_void_p,
											   ctypes.c_void_p,
											   ctypes.c_void_p,
											   ctypes.c_void_p]
cf.CFURLCopyResourcePropertyForKey.restype = ctypes.c_int

cf.CFBooleanGetValue.argtypes = [ctypes.c_void_p]
cf.CFBooleanGetValue.restype = ctypes.c_int

cf.CFURLEnumeratorCreateForDirectoryURL.argtypes = [ctypes.c_void_p,
													ctypes.c_void_p,
													ctypes.c_int,
													ctypes.c_void_p]
cf.CFURLEnumeratorCreateForDirectoryURL.restype = ctypes.c_void_p

cf.CFURLEnumeratorGetNextURL.argtypes = [ctypes.c_void_p,
										 ctypes.c_void_p,
										 ctypes.c_void_p]
cf.CFURLEnumeratorGetNextURL.restype = ctypes.c_int

cf.CFURLCopyFileSystemPath.argtypes = [ctypes.c_void_p, ctypes.c_int]
cf.CFURLCopyFileSystemPath.restype = ctypes.c_void_p

# From CFString.h
# http://www.opensource.apple.com/source/CF/CF-744/CFString.h
# The value has been the same from at least 10.2-10.8.
kCFStringEncodingUTF8 = 0x08000100

# Documented here:
# https://developer.apple.com/library/mac/#documentation/CoreFoundation/Reference/CFURLEnumeratorRef/Reference/reference.html
kCFURLEnumeratorSkipInvisibles = 1 << 1

kCFURLEnumeratorSuccess = 1
kCFURLEnumeratorEnd = 2
kCFURLEnumeratorError = 3
kCFURLEnumeratorDirectoryPostOrderSuccess = 4

# Documented here:
# http://developer.apple.com/library/ios/#documentation/CoreFoundation/Reference/CFURLRef/Reference/reference.html
kCFURLPOSIXPathStyle = 0

# This one is a static CFStringRef.
kCFURLIsHiddenKey = ctypes.c_void_p.in_dll(cf, 'kCFURLIsHiddenKey')

@contextlib.contextmanager
def cfreleasing(stuff):
	try:
		yield
	finally:
		for thing in stuff:
			cf.CFRelease(thing)

def cfstr_to_unicode(cfstr):
	count = cf.CFStringGetMaximumSizeOfFileSystemRepresentation(cfstr)
	buf = (ctypes.c_char * count)()
	if cf.CFStringGetFileSystemRepresentation(cfstr, buf, count):
		return buf.value.decode('UTF-8')
	raise OSError('CFStringGetFileSystemRepresentation failed')

def is_hidden(path):
	if not isinstance(path, bytes):
		path = path.encode('UTF-8')
	stuff = []
	with cfreleasing(stuff):
		url = cf.CFURLCreateFromFileSystemRepresentation(None, path, len(path),
														 False)
		stuff.append(url)
		val = ctypes.c_void_p(0)
		ret = cf.CFURLCopyResourcePropertyForKey(url, kCFURLIsHiddenKey,
												 ctypes.addressof(val), None)
		if ret:
			result = cf.CFBooleanGetValue(val)
			stuff.append(val)
			return True if result else False
		# TODO: You could pass a CFErrorRef instead of None, and do all the
		# work to wrap that in a Python exception, etc.
		raise OSError('CFURLCopyResourcePropertyForKey failed')