from fman.impl.view import diff_lists, apply_list_diff
from unittest import TestCase

class DiffListsTest(TestCase):
	def test_empty(self):
		self.assertEqual([], diff_lists([], []))
	def test_start_from_empty(self):
		self.assertEqual([[1]], diff_lists([], [1]))
	def test_equal(self):
		self.assertEqual([[1], [2]], diff_lists([1, 2], [1, 2]))
	def test_new_longer(self):
		self.assertEqual(
			[[1], [2, 3], [4, 5]], diff_lists([1, 3, 5], [1, 2, 3, 4, 5])
		)
	def test_new_shorter(self):
		self.assertEqual([[1], [], [3]], diff_lists([1, 2, 3], [1, 3]))
	def test_completely_different(self):
		self.assertEqual([[], [], [4, 5]], diff_lists([1, 2, 3], [4, 5]))

class ApplyListDiffTest(TestCase):
	def test_empty(self):
		self._test([], [])
	def test_start_from_empty(self):
		self._test([], [1])
	def test_equal(self):
		self._test([1, 2], [1, 2])
	def test_new_longer(self):
		self._test([1, 3, 7], [0, 1, 2, 3, 4, 5, 6, 7, 8])
	def test_new_shorter(self):
		self._test([1, 2, 3], [1, 3])
	def test_completely_different(self):
		self._test([1, 2, 3], [4, 5])
	def _test(self, old, new):
		diff = diff_lists(old, new)
		merged = old[:]
		apply_list_diff(diff, merged)
		self.assertEqual(new, merged)
