from core.commands import SuggestLocations, History, Move
from core.tests import StubUI
from fman import OK, YES, NO
from fman.util.system import is_linux, is_windows
from os import mkdir
from os.path import normpath, join
from unittest import TestCase, skipIf
from tempfile import TemporaryDirectory

import os

class ConfirmTreeOperationTest(TestCase):
	def test_no_files(self):
		self._expect_alert(('No file is selected!',), answer=OK)
		self.assertIsNone(self._run([], '', ''))
	def test_one_file(self):
		dest_path = join(self._dest, 'a.txt')
		self._expect_prompt(('Move "a.txt" to', dest_path), (dest_path, True))
		self.assertEqual(
			(self._dest, 'a.txt'),
			self._run([self._a_txt], self._dest, self._src)
		)
	def test_one_dir(self):
		self._expect_prompt(('Move "a" to', self._dest), (self._dest, True))
		self.assertEqual(
			(self._dest, None),
			self._run([self._a], self._dest, self._src)
		)
	def test_two_files(self):
		self._expect_prompt(('Move 2 files to', self._dest), (self._dest, True))
		self.assertEqual(
			(self._dest, None),
			self._run([self._a_txt, self._b_txt], self._dest, self._src)
		)
	def test_into_subfolder(self):
		dest_path = join(self._dest, 'a.txt')
		self._expect_prompt(('Move "a.txt" to', dest_path), ('a', True))
		self.assertEqual(
			(self._a, None),
			self._run([self._a_txt], self._dest, self._src)
		)
	def test_overwrite_single_file(self):
		dest_path = join(self._dest, 'a.txt')
		self._touch(dest_path)
		self._expect_prompt(('Move "a.txt" to', dest_path), (dest_path, True))
		self.assertEqual(
			(self._dest, 'a.txt'),
			self._run([self._a_txt], self._dest, self._src)
		)
	def test_multiple_files_over_one(self):
		dest_path = join(self._dest, 'a.txt')
		self._touch(dest_path)
		self._expect_prompt(('Move 2 files to', self._dest), (dest_path, True))
		self._expect_alert(
			('You cannot move multiple files to a single file!',), answer=OK
		)
		self.assertIsNone(
			self._run([self._a_txt, self._b_txt], self._dest, self._src)
		)
	def test_renamed_destination(self):
		self._expect_prompt(
			('Move "a.txt" to', join(self._dest, 'a.txt')),
			(join(self._dest, 'z.txt'), True)
		)
		self.assertEqual(
			(self._dest, 'z.txt'),
			self._run([self._a_txt], self._dest, self._src)
		)
	def test_multiple_files_nonexistent_dest(self):
		dest = join(self._dest, 'dir')
		self._expect_prompt(
			('Move 2 files to', self._dest),
			(dest, True)
		)
		self._expect_alert(
			('%s does not exist. Do you want to create it as a directory and '
			 'move the files there?' % dest, YES | NO, YES),
			answer=YES
		)
		self.assertEqual(
			(dest, None),
			self._run([self._a_txt, self._b_txt], self._dest, self._src)
		)
	def _expect_alert(self, args, answer):
		self._ui.expect_alert(args, answer)
	def _expect_prompt(self, args, answer):
		self._ui.expect_prompt(args, answer)
	def _run(self, files, dest_dir, src_dir):
		result = \
			Move._confirm_tree_operation(files, dest_dir, src_dir, self._ui)
		self._ui.verify_expected_dialogs_were_shown()
		return result
	def setUp(self):
		super().setUp()
		self._ui = StubUI(self)
		self._temp_dir = TemporaryDirectory()
		self._src = join(self._temp_dir.name, 'src')
		mkdir(self._src)
		self._dest = join(self._temp_dir.name, 'dest')
		mkdir(self._dest)
		self._a = join(self._src, 'a')
		mkdir(self._a)
		self._a_txt = join(self._src, 'a.txt')
		self._touch(self._a_txt)
		self._b_txt = join(self._src, 'b.txt')
		self._touch(self._b_txt)
	def tearDown(self):
		self._temp_dir.cleanup()
		super().tearDown()
	def _touch(self, file_path):
		with open(file_path, 'w'): pass

class SuggestLocationsTest(TestCase):
	def test_empty_suggests_recent_locations(self):
		expected_paths = [
			'~/Dropbox/Work', '~/Dropbox', '~/Downloads', '~/Dropbox/Private',
			'~'
		]
		self._check_query_returns(
			'', expected_paths, [[]] * len(expected_paths)
		)
	def test_basename_matches(self):
		self._check_query_returns(
			'dow', ['~/Downloads', '~/Dropbox/Work'], [[2, 3, 4], [2, 4, 10]]
		)
	def test_exact_match_takes_precedence(self):
		expected_paths = \
			['~', '~/Dropbox', '~/Downloads', '~/.hidden', '~/Unvisited']
		self._check_query_returns(
			'~', expected_paths, [[0]] * len(expected_paths)
		)
	def test_prefix_match(self):
		self._check_query_returns('~/dow', ['~/Downloads'], [[0, 1, 2, 3, 4]])
	def test_matches_upper_characters(self):
		self._check_query_returns(
			'dp', ['~/Dropbox/Private', '~/Dropbox/Work', '~/Dropbox'],
			[[2, 10], [2, 5], [2, 5]]
		)
	def test_existing_path(self):
		self._check_query_returns(
			'~/Unvisited', ['~/Unvisited', '~/Unvisited/Dir']
		)
	@skipIf(is_linux(), 'Case-insensitive file systems only')
	def test_existing_path_wrong_case(self):
		self._check_query_returns(
			'~/unvisited', ['~/Unvisited', '~/Unvisited/Dir']
		)
	def test_enter_path_slash(self):
		highlight = list(range(len('~/Unvisited')))
		self._check_query_returns(
			'~/Unvisited/', ['~/Unvisited', '~/Unvisited/Dir'],
			[highlight, highlight]
		)
	def test_trailing_space(self):
		self._check_query_returns('~/Downloads ', [])
	def test_hidden(self):
		self._check_query_returns('~/.', ['~/.hidden'])
	def test_filesystem_search(self):
		# No visited paths:
		self.instance = SuggestLocations({}, self.file_system)
		# Should still find Downloads by prefix:
		self._check_query_returns('dow', ['~/Downloads'], [[2, 3, 4]])
	def setUp(self):
		visited_paths = {
			'~': 1,
			self._replace_pathsep('~/Downloads'): 3,
			self._replace_pathsep('~/Dropbox'): 4,
			self._replace_pathsep('~/Dropbox/Work'): 5,
			self._replace_pathsep('~/Dropbox/Private'): 2
		}
		root = 'C:' if is_windows() else ''
		files = {
			root: {
				'Users': {
					'michael': {
						'.hidden': {},
						'Downloads': {},
						'Dropbox': {
							'Work': {}, 'Private': {}
						},
						'Unvisited': {
							'Dir': {}
						}
					}
				}
			},
			'.': {}
		}
		if is_windows():
			home_dir = r'C:\Users\michael'
		else:
			home_dir = '/Users/michael'
		self.file_system = StubFileSystem(files, home_dir=home_dir)
		self.instance = SuggestLocations(visited_paths, self.file_system)
	def _check_query_returns(self, query, paths, highlights=None):
		query = self._replace_pathsep(query)
		paths = list(map(self._replace_pathsep, paths))
		if highlights is None:
			highlights = [self._full_range(query)] * len(paths)
		result = list(self.instance(query))
		actual_paths = [item.value for item in result]
		actual_highlights = [item.highlight for item in result]
		self.assertEqual(paths, actual_paths)
		self.assertEqual(highlights, actual_highlights)
	def _replace_pathsep(self, path):
		return path.replace('/', os.sep)
	def _full_range(self, string):
		return list(range(len(string)))

class StubFileSystem:
	def __init__(self, files, home_dir):
		self.files = files
		self.home_dir = home_dir
	def isdir(self, path):
		if is_windows() and path.endswith(' '):
			# Strange behaviour on Windows: isdir('X ') returns True if X
			# (without space) exists.
			path = path.rstrip(' ')
		try:
			self._get_dir(path)
		except KeyError:
			return False
		return True
	def _get_dir(self, path):
		if not path:
			raise KeyError(path)
		path = normpath(path)
		parts = path.split(os.sep) if path != os.sep else ['']
		if len(parts) > 1 and parts[-1] == '':
			parts = parts[:-1]
		curr = self.files
		for part in parts:
			for file_name, items in curr.items():
				if self._normcase(file_name) == self._normcase(part):
					curr = items
					break
			else:
				raise KeyError(part)
		return curr
	def expanduser(self, path):
		return path.replace('~', self.home_dir)
	def listdir(self, path):
		try:
			return sorted(list(self._get_dir(path)))
		except KeyError as e:
			raise FileNotFoundError(repr(path)) from e
	def samefile(self, f1, f2):
		return self._get_dir(f1) == self._get_dir(f2)
	def find_folders_starting_with(self, prefix):
		return list(self._find_folders_recursive(self.files, prefix.lower()))
	def _find_folders_recursive(self, files, prefix):
		for f, subfiles in files.items():
			if f.lower().startswith(prefix):
				yield f
			for sub_f in self._find_folders_recursive(subfiles, prefix):
				# We don't use join(...) here because of the case f=''. We want
				# '/sub_f' but join(f, sub_f) would give just 'sub_f'.
				yield f + os.sep + sub_f
	def _normcase(self, path):
		return path if is_linux() else path.lower()

class HistoryTest(TestCase):
	def test_empty_back(self):
		with self.assertRaises(ValueError):
			self._go_back()
	def test_empty_forward(self):
		with self.assertRaises(ValueError):
			self._go_forward()
	def test_single_back(self):
		self._go_to('single item')
		with self.assertRaises(ValueError):
			self._go_back()
	def test_single_forward(self):
		self._go_to('single item')
		with self.assertRaises(ValueError):
			self._go_forward()
	def test_go_back_forward(self):
		self._go_to('a', 'b', 'c')
		self.assertEqual('b', self._go_back())
		self.assertEqual('a', self._go_back())
		self.assertEqual('b', self._go_forward())
		self.assertEqual('c', self._go_forward())
	def test_go_to_after_back(self):
		self._go_to('a', 'b')
		self.assertEqual('a', self._go_back())
		self._go_to('c')
		self.assertEqual(['a', 'c'], self._history._paths)
	def setUp(self):
		super().setUp()
		self._history = History()
	def _go_back(self):
		path = self._history.go_back()
		self._history.path_changed(path)
		return path
	def _go_forward(self):
		path = self._history.go_forward()
		self._history.path_changed(path)
		return path
	def _go_to(self, *paths):
		for path in paths:
			self._history.path_changed(path)