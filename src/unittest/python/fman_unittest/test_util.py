from fman.impl.util import is_below_dir, CachedIterable
from fman.impl.util.system import is_windows
from os.path import join
from unittest import TestCase, skipIf

class IsBelowDirTest(TestCase):
	def test_direct_subdir(self):
		self.assertTrue(is_below_dir(join(self.root, 'subdir'), self.root))
	def test_self(self):
		self.assertFalse(is_below_dir(self.root, self.root))
	def test_nested_subdir(self):
		nested = join(self.root, 'subdir', 'nested')
		self.assertTrue(is_below_dir(nested, self.root))
	@skipIf(not is_windows(), 'Skipping Windows-only test')
	def test_different_drive_windows(self):
		self.assertFalse(is_below_dir(r'c:\Dir\Subdir', r'D:\Dir'))
	def setUp(self):
		self.root = r'C:\Dir' if is_windows() else '/Dir'

class CachedIterableTest(TestCase):
	def test_simple(self):
		# For the sake of illustration, see what happens normally:
		iterable = self._generate(1, 2, 3)
		self.assertEqual([1, 2, 3], list(iterable))
		self.assertEqual([], list(iterable))
		# Now compare the above to what happens with CachedIterable:
		iterable = CachedIterable(self._generate(1, 2, 3))
		self.assertEqual([1, 2, 3], list(iterable))
		self.assertEqual([1, 2, 3], list(iterable))
	def test_remove_after_cached(self):
		iterable = CachedIterable(self._generate(1, 2, 3))
		iterator = iter(iterable)
		self.assertEqual(1, next(iterator))
		iterable.remove(1)
		self.assertEqual(2, next(iterator))
		self.assertEqual(3, next(iterator))
		self.assertEqual([2, 3], list(iterable))
	def test_remove_before_cached(self):
		iterable = CachedIterable(self._generate(1, 2, 3))
		iterator = iter(iterable)
		self.assertEqual(1, next(iterator))
		iterable.remove(2)
		self.assertEqual(3, next(iterator))
		with self.assertRaises(StopIteration):
			next(iterator)
		self.assertEqual([1, 3], list(iterable))
	def test_add_before_exhausted(self):
		iterable = CachedIterable(self._generate(1, 2))
		iterator = iter(iterable)
		self.assertEqual(1, next(iterator))
		iterable.add(3)
		self.assertEqual(2, next(iterator))
		self.assertEqual(3, next(iterator))
		self.assertEqual([1, 2, 3], list(iterable))
		self.assertEqual([1, 2, 3], list(iterable))
	def test_add_after_exhausted(self):
		iterable = CachedIterable(self._generate(1, 2))
		self.assertEqual([1, 2], list(iterable))
		iterable.add(3)
		self.assertEqual([1, 2, 3], list(iterable))
		self.assertEqual([1, 2, 3], list(iterable))
	def test_add_duplicate(self):
		iterable = CachedIterable(self._generate(1, 2))
		iterable.add(2)
		self.assertEqual([1, 2], list(iterable))
		self.assertEqual([1, 2], list(iterable))
	def test_add_duplicate_after_exhausted(self):
		iterable = CachedIterable(self._generate(1, 2))
		self.assertEqual([1, 2], list(iterable))
		iterable.add(2)
		self.assertEqual([1, 2], list(iterable))
	def _generate(self, *args):
		yield from args