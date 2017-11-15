from core import DefaultFileSystem
from fman.url import splitscheme

class StubUI:
	def __init__(self, test_case):
		self._expected_alerts = []
		self._expected_prompts = []
		self._test_case = test_case
	def expect_alert(self, args, answer):
		self._expected_alerts.append((args, answer))
	def expect_prompt(self, args, answer):
		self._expected_prompts.append((args, answer))
	def verify_expected_dialogs_were_shown(self):
		self._test_case.assertEqual(
			[], self._expected_alerts, 'Did not receive all expected alerts.'
		)
		self._test_case.assertEqual(
			[], self._expected_prompts, 'Did not receive all expected prompts.'
		)
	def show_alert(self, *args, **_):
		if not self._expected_alerts:
			self._test_case.fail('Unexpected alert: %r' % args[0])
			return
		expected_args, answer = self._expected_alerts.pop(0)
		self._test_case.assertEqual(expected_args, args, "Wrong alert")
		return answer
	def show_prompt(self, *args, **_):
		if not self._expected_prompts:
			self._test_case.fail('Unexpected prompt: %r' % args[0])
			return
		expected_args, answer = self._expected_prompts.pop(0)
		self._test_case.assertEqual(expected_args, args, "Wrong prompt")
		return answer
	def show_status_message(self, _):
		pass
	def clear_status_message(self):
		pass

class StubFS:
	def __init__(self):
		self._impl = DefaultFileSystem()
	def is_dir(self, url):
		return self._impl.is_dir(self._as_path(url))
	def exists(self, url):
		return self._impl.exists(self._as_path(url))
	def samefile(self, url1, url2):
		return self._impl.samefile(self._as_path(url1), self._as_path(url2))
	def iterdir(self, url):
		return self._impl.iterdir(self._as_path(url))
	def makedirs(self, url, exist_ok=False):
		self._impl.makedirs(self._as_path(url), exist_ok=exist_ok)
	def copy(self, src_url, dst_url):
		self._impl.copy(src_url, dst_url)
	def delete(self, url):
		self._impl.delete(self._as_path(url))
	def move(self, src_url, dst_url):
		self._impl.move(src_url, dst_url)
	def touch(self, url):
		self._impl.touch(self._as_path(url))
	def mkdir(self, url):
		self._impl.mkdir(self._as_path(url))
	def _as_path(self, url):
		scheme, path = splitscheme(url)
		if scheme != 'file://':
			raise ValueError(
				'This stub implementation only supports file:// urls.'
			)
		return path