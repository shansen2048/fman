from fman import PLATFORM
from fman.impl.plugins import ExternalPlugin
from fman.impl.plugins.config import Config
from fman.impl.plugins.key_bindings import KeyBindings
from fman_integrationtest import get_resource
from fman_integrationtest.impl.plugins import StubErrorHandler, \
	StubCommandCallback, StubTheme
from os.path import join
from unittest import TestCase

import json

class ExternalPluginTest(TestCase):
	def test_load(self):
		error_handler = StubErrorHandler()
		command_callback = StubCommandCallback()
		key_bindings = KeyBindings()
		plugin_dir = get_resource('Simple Plugin')
		config = Config(PLATFORM)
		plugin = ExternalPlugin(
			error_handler, command_callback, key_bindings, plugin_dir, config,
			StubTheme()
		)

		plugin.load()

		with open(join(plugin_dir, 'Key Bindings.json'), 'r') as f:
			bindings_raw = json.load(f)
		self.assertEquals(bindings_raw, config.load_json('Key Bindings.json'))
		self.assertEquals(bindings_raw, key_bindings.get_sanitized_bindings())