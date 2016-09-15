from fman import platform

if platform() == 'osx':
	from osxtrash import move_to_trash
else:
	from send2trash import send2trash
	def move_to_trash(*files):
		for file in files:
			send2trash(file)