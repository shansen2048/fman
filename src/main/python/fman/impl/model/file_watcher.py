from fman.url import dirname
from threading import Lock

class FileWatcher:
	def __init__(self, fs, model):
		self._fs = fs
		self._model = model
		self._lock = Lock()
	def start(self):
		with self._lock:
			self._fs.file_added.add_callback(self._on_file_added)
			self._fs.file_moved.add_callback(self._on_file_moved)
			self._fs.file_removed.add_callback(self._on_file_removed)
			self._fs.add_file_changed_callback(
				self._model.get_location(), self._on_file_changed
			)
	def shutdown(self):
		with self._lock:
			try:
				self._fs.remove_file_changed_callback(
					self._model.get_location(), self._on_file_changed
				)
				self._fs.file_removed.remove_callback(self._on_file_removed)
				self._fs.file_moved.remove_callback(self._on_file_moved)
				self._fs.file_added.remove_callback(self._on_file_added)
			except ValueError:
				pass
	def _on_file_added(self, url):
		if self._is_in_root(url):
			self._model.notify_file_changed(url)
	def _on_file_moved(self, old_url, new_url):
		new_is_in_root = self._is_in_root(new_url)
		if self._is_in_root(old_url):
			if new_is_in_root:
				self._model.notify_file_renamed(old_url, new_url)
			else:
				self._on_file_removed(old_url)
		else:
			if new_is_in_root:
				self._on_file_added(new_url)
	def _on_file_removed(self, url):
		if self._is_in_root(url):
			self._model.notify_file_changed(url)
	def _on_file_changed(self, url):
		if url == self._model.get_location():
			# The common case
			self._model.reload()
		elif self._is_in_root(url):
			self._model.notify_file_changed(url)
	def _is_in_root(self, url):
		return dirname(url) == self._model.get_location()