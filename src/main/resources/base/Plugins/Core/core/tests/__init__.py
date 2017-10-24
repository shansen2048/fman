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
		self._test_case.assertEqual(expected_args, args)
		return answer
	def show_prompt(self, *args, **_):
		if not self._expected_prompts:
			self._test_case.fail('Unexpected prompt: %r' % args[0])
			return
		expected_args, answer = self._expected_prompts.pop(0)
		self._test_case.assertEqual(expected_args, args)
		return answer
	def show_status_message(self, _):
		pass
	def clear_status_message(self):
		pass