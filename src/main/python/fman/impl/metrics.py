from collections import deque
from queue import Queue
from threading import Thread
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import urlopen, Request
from os import makedirs
from os.path import dirname

import json

class MetricsError(Exception):
	pass

class Metrics:
	def __init__(self, json_path, backend, os, fman_version):
		self._json_path = json_path
		self._backend = backend
		self._os = os
		self._fman_version = fman_version
		self._user = None
		self._enabled = True
	def initialize(self):
		try:
			with open(self._json_path, 'r') as f:
				json_dict = json.load(f)
		except FileNotFoundError:
			try:
				self._user = self._backend.create_user()
			except MetricsError:
				self._enabled = False
			else:
				makedirs(dirname(self._json_path), exist_ok=True)
				with open(self._json_path, 'w') as f:
					json.dump({'user': self._user}, f)
		else:
			self._enabled = json_dict.get('enabled', True)
			try:
				self._user = json_dict['user']
			except KeyError:
				# TODO: Replace this by `self._enabled = False` after June 2017
				self._migrate_from_uuid(json_dict)
	def track(self, event, properties=None):
		if not self._enabled:
			return
		data = {
			'os': self._os,
			'app_version': self._fman_version
		}
		if properties:
			data.update(properties)
		try:
			self._backend.track(self._user, event, data)
		except MetricsError:
			pass
	def _migrate_from_uuid(self, json_dict):
		try:
			self._user = json_dict['uuid']
		except KeyError:
			self._enabled = False
		else:
			json_dict['user'] = json_dict.pop('uuid')
			with open(self._json_path, 'w') as f:
				json.dump(json_dict, f)

class ServerBackend:
	@classmethod
	def get_data_for_tracking(cls, user, event, properties=None):
		result = {
			'user': user,
			'event': event
		}
		if properties:
			result.update(properties)
		return result
	def __init__(self, users_url, events_url):
		self._users_url = users_url
		self._events_url = events_url
	def create_user(self):
		return self._post(self._users_url)
	def track(self, user, event, properties=None):
		data = self.get_data_for_tracking(user, event, properties)
		self._post(self._events_url, data)
	def _post(self, url, data=None):
		encoded_data = urlencode(data).encode('utf-8') if data else None
		try:
			with urlopen(Request(url, encoded_data, method='POST')) as response:
				resp_body = response.read()
		except URLError as e:
			raise MetricsError() from e
		if response.status // 100 != 2:
			raise MetricsError('Unexpected HTTP status %d.' % response.status)
		try:
			return resp_body.decode('utf-8')
		except ValueError:
			raise MetricsError('Unexpected response: %r' % resp_body)

class LoggingBackend:
	def __init__(self, max_num_logs=1000):
		self._logs = deque(maxlen=max_num_logs)
	def create_user(self):
		raise MetricsError('Not implemented')
	def track(self, user, event, properties=None):
		data = ServerBackend.get_data_for_tracking(user, event, properties)
		self._logs.append(data)
	def flush(self, log_file_path):
		with open(log_file_path, 'w') as f:
			fmt_log = lambda data: json.dumps(data, indent=4)
			f.write('\n\n'.join(map(fmt_log, self._logs)))

class AsynchronousMetrics:
	def __init__(self, metrics):
		self._metrics = metrics
		self._queue = Queue()
		self._thread = Thread(target=self._work, daemon=True)
	def initialize(self, *args, **kwargs):
		self._queue.put(('initialize', args, kwargs))
		self._thread.start()
	def track(self, *args, **kwargs):
		self._queue.put(('track', args, kwargs))
	def _work(self):
		while True:
			method_name, args, kwargs = self._queue.get()
			getattr(self._metrics, method_name)(*args, **kwargs)
			self._queue.task_done()