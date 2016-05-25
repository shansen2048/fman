from subprocess import Popen

class OS:
	def move_to_trash(self, *files):
		raise NotImplementedError()
	def prompt_user_to_pick_application(self, message):
		raise NotImplementedError()
	def open(self, *files, with_app=None):
		raise NotImplementedError()

class OSX(OS):
	def move_to_trash(self, *files):
		from osxtrash import move_to_trash
		return move_to_trash(*files)
	def prompt_user_to_pick_application(self, message):
		# Note: This import takes 200ms. Don't do it at the top of a file!
		from Cocoa import NSOpenPanel, NSURL, NSOKButton
		panel = NSOpenPanel.openPanel()
		panel.setDirectoryURL_(NSURL.fileURLWithPath_('/Applications'))
		panel.setCanChooseDirectories_(False)
		panel.setAllowedFileTypes_(['app'])
		panel.setMessage_(title)
		result = panel.runModal()
		if result == NSOKButton:
			return panel.filename()
	def open(self, *files, with_app=None):
		args = ['/usr/bin/open']
		if with_app:
			args += ['-a', with_app]
		args.extend(files)
		Popen(args)