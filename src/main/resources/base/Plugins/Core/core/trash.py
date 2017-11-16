from fman import PLATFORM

if PLATFORM == 'Mac':
	from osxtrash import move_to_trash
else:
	def move_to_trash(*files):
		# We import send2trash as late as possible. Here's why: On Ubuntu
		# (/Gnome), send2trash uses GIO - if it is available and initialized.
		# Whether that happens is determined at *import time*. Importing
		# send2trash at the last possible moment, ensures that it picks up GIO.
		from send2trash import send2trash
		for file in files:
			send2trash(file)