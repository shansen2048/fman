from fman.impl.plugins.error import PluginErrorHandler, format_traceback
from fman.impl.plugins.plugin import CommandWrapper
from fman_integrationtest import get_resource
from os.path import dirname
from unittest import TestCase

import re
import sys

class FormatTracebackTest(TestCase):
	def test_format_traceback(self):
		import fman_
		import plugin.module
		try:
			fman_.run_plugins()
		except ValueError as e:
			exc = e
		exclude_from_tb = [dirname(__file__), dirname(fman_.__file__)]
		traceback_ = format_traceback(exc, exclude_from_tb)
		self.assertEqual(
			'Traceback (most recent call last):\n'
			'  File "' + plugin.module.__file__ + '", line 4, in run_plugin\n'
			'    raise_error()\n'
			'ValueError\n',
			traceback_
		)
	def setUp(self):
		sys.path.append(get_resource('FormatTracebackTest'))
		self.maxDiff = None
	def tearDown(self):
		sys.path.pop()

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
		self.error_handler = PluginErrorHandler(None, None)
	class _RaiseError:
		def __call__(self):
			raise ValueError()