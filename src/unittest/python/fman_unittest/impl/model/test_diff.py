from fman.impl.model.diff import DiffEntry, ComputeDiff
from itertools import chain, combinations
from unittest import TestCase

class ComputeDiffTest(TestCase):
	def test_empty(self):
		self._check_diff([], [], [])
	def test_same(self):
		rows = [self._a, self._b, self._c]
		self._check_diff(rows, rows, [])
	def test_add_into_empty(self):
		rows = [self._a, self._b]
		self._check_diff([], rows, [(0, 0, 0, rows)])
	def test_insert_before(self):
		base = [self._c]
		extra = [self._a, self._b]
		self._check_diff(base, extra + base, [(0, 0, 0, extra)])
	def test_insert_after(self):
		base = [self._a]
		extra = [self._b, self._c]
		self._check_diff(base, base + extra, [(0, 0, 1, extra)])
	def test_insert_between(self):
		self._check_diff(
			[self._a, self._c],
			[self._a, self._b, self._c],
			[(0, 0, 1, [self._b])]
		)
	def test_reorder_rows(self):
		self._check_diff(
			[self._a, self._b],
			[self._b, self._a],
			[(1, 2, 0, [self._b])]
		)
	def test_powerset_combinations(self, max_num_rows=5):
		for old in _powerset(range(max_num_rows)):
			for new in _powerset(range(max_num_rows)):
				pathify = lambda s: [(str(i), i) for i in s]
				self._check_diff(pathify(old), pathify(new))
	def test_clear(self):
		self._check_diff([self._a, self._b], [], [(0, 2, 0, [])])
	def setUp(self):
		super().setUp()
		self._a = ('a', 1)
		self._b = ('b', 2)
		self._c = ('c', 3)
	def _check_diff(self, old, new, expected_diff_tpls=None):
		diff = ComputeDiff(old, new)()
		old_patched = self._apply_diff(diff, old)
		self.assertEqual(
			new, old_patched,
			'Diff %r for %r -> %r is incorrect!' % (diff, old, new)
		)
		if expected_diff_tpls is not None:
			expected_diff = [DiffEntry(*entry) for entry in expected_diff_tpls]
			self.assertEqual(expected_diff, diff)
	def _apply_diff(self, diff, old):
		result = list(old)
		for entry in diff:
			result = result[:entry.cut_start] + result[entry.cut_end:]
			result = result[:entry.insert_start] + entry.rows + \
					 result[entry.insert_start:]
		return result

def _powerset(iterable):
	s = list(iterable)
	return chain.from_iterable(combinations(s, r) for r in range(len(s) + 1))