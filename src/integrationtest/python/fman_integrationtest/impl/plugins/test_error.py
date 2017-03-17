from fman.impl.plugins.error import PluginErrorHandler
from fman.impl.plugins.plugin import CommandWrapper
from os.path import dirname
from unittest import TestCase

import re

class CommandWrapper_PluginErrorHandler_IntegrationTest(TestCase):
	def test_traceback(self):
		wrapper = CommandWrapper(self._RaiseError(), self.error_handler)
		wrapper()
		actual_message, = self.error_handler.pending_error_messages
		# Note how the expected message doesn't contain any traceback entries
		# from fman's source code tree:
		expected_message = \
			"Command '_RaiseError' raised exception.\n\n" \
			"Traceback (most recent call last):\n" \
			"  File \"%s\", line 176, in __call__\n" \
			"    raise ValueError()\n" \
			"ValueError\n" % __file__
		expected_msg_re = re.escape(expected_message).replace('176', r'\d+')
		self.assertRegex(actual_message, expected_msg_re)
	def setUp(self):
		plugin_dir = dirname(dirname(__file__))
		self.error_handler = PluginErrorHandler([plugin_dir], None, None)
	class _RaiseError:
		def __call__(self):
			raise ValueError()
