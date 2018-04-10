from fman.impl.util.qt.thread import run_in_main_thread

class FileWatcher:
	"""
	Say we're at ~/Downloads and the user presses Backspace to go up to ~.
	Here's what typically happens:
	 1) we "unwatch" ~/Downloads
	 2) we load and display the files in ~
	 3) we "watch" ~.

	Now consider what happens if the user presses Backspace *before* ~/Downloads
	was fully loaded, ie. we're still at step 2) above. In this case, we are
	not yet "watching" ~/Downloads but are already executing step 1), which is
	to "unwatch" it. This produces an error.

	The purpose of this helper class is to solve the above problem. It remembers
	which paths are actually being watched and offers a #clear() method that
	unwatches precisely those paths. This way, only paths that were actually
	watched are ever "unwatched".
	"""
	def __init__(self, fs, callback):
		self._fs = fs
		self._callback = callback
		self._watched_files = []
	# Run in main thread to synchronize access and also because some FS watchers
	# may need to be run in the main thread (eg. LocalFileSystem).
	@run_in_main_thread
	def watch(self, url):
		self._fs.add_file_changed_callback(url, self._callback)
		self._watched_files.append(url)
	# Run in main thread to synchronize access and also because some FS watchers
	# may need to be run in the main thread (eg. LocalFileSystem).
	@run_in_main_thread
	def clear(self):
		for url in self._watched_files:
			self._fs.remove_file_changed_callback(url, self._callback)
		self._watched_files = []
