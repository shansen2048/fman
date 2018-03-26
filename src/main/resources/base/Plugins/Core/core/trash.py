from fman import PLATFORM

if PLATFORM == 'Mac':
	from osxtrash import move_to_trash
else:
	def move_to_trash(*files):
		send2trash = _import_send2trash()
		for file in files:
			send2trash(file)

def _import_send2trash():
	# We import send2trash as late as possible. Here's why: On Ubuntu
	# (/Gnome), send2trash uses GIO - if it is available and initialized.
	# Whether that happens is determined at *import time*. Importing
	# send2trash at the last possible moment, ensures that it picks up GIO.
	from send2trash import send2trash as result
	if PLATFORM == 'Linux':
		try:
			from gi.repository import GObject
		except ImportError:
			pass
		else:
			# Fix for elementary OS / Pantheon:
			if not hasattr(GObject, 'GError'):
				from send2trash.plat_other import send2trash as result
	return result