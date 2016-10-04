from concurrent.futures import ThreadPoolExecutor
from getpass import getuser
from mixpanel import Mixpanel
from os import makedirs
from os.path import dirname
from uuid import uuid4

import json

class Tracker:
	def __init__(self, mixpanel_token, json_path):
		self.mp = Mixpanel(mixpanel_token)
		self.json_path = json_path
		self.super_properties = {}
		self.collect_statistics = True
		self.user_id = None
		self._executor = ThreadPoolExecutor(max_workers=1)
	def initialize(self):
		try:
			with open(self.json_path, 'r') as f:
				json_dict = json.load(f)
		except FileNotFoundError:
			self.user_id = str(uuid4())
			self._executor.submit(
				self.mp.people_set, self.user_id, {'$name': getuser()}
			)
			makedirs(dirname(self.json_path), exist_ok=True)
			with open(self.json_path, 'w') as f:
				json.dump({'uuid': self.user_id}, f)
		else:
			self.collect_statistics = json_dict.get('collect_statistics', True)
			try:
				self.user_id = json_dict['uuid']
			except KeyError:
				pass
	def track(self, event_name, properties=None):
		if not self.collect_statistics:
			return
		props = dict(self.super_properties)
		if properties:
			props.update(properties)
		self._executor.submit(self.mp.track, self.user_id, event_name, props)