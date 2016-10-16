from core.commands import SuggestLocations
from fman import platform
from os.path import normpath
from unittest import TestCase

import os

class SuggestLocationsTest(TestCase):
	def test_empty_suggests_recent_locations(self):
		expected_paths = (
			'~/Dropbox/Work', '~/Dropbox', '~/Downloads', '~/Dropbox/Private',
			'~'
		)
		self._check_query_returns(
			'', expected_paths, ([],) * len(expected_paths)
		)
	def test_basename_matches(self):
		self._check_query_returns(
			'dow', ('~/Downloads', '~/Dropbox/Work'), ([2, 3, 4], [2, 4, 10])
		)
	def test_exact_match_takes_precedence(self):
		expected_paths = \
			('~', '~/Dropbox', '~/Downloads', '~/.hidden', '~/Unvisited')
		self._check_query_returns(
			'~', expected_paths, ([0],) * len(expected_paths)
		)
	def test_prefix_match(self):
		self._check_query_returns('~/dow', ('~/Downloads',), ([0, 1, 2, 3, 4],))
	def test_matches_upper_characters(self):
		self._check_query_returns(
			'dp', ('~/Dropbox/Private', '~/Dropbox/Work', '~/Dropbox'),
			([2, 10], [2, 5], [2, 5])
		)
	def test_enter_existing_path(self):
		self._check_query_returns(
			'~/Unvisited', ('~/Unvisited', '~/Unvisited/Dir')
		)
	def test_enter_path_slash(self):
		self._check_query_returns(
			'~/Unvisited/', ('~/Unvisited/', '~/Unvisited/Dir',)
		)
	def test_hidden(self):
		self._check_query_returns('~/.', ('~/.hidden',))
	def setUp(self):
		recent_locations = {
			'~': 1,
			self._replace_pathsep('~/Downloads'): 3,
			self._replace_pathsep('~/Dropbox'): 4,
			self._replace_pathsep('~/Dropbox/Work'): 5,
			self._replace_pathsep('~/Dropbox/Private'): 2
		}
		root = 'C:' if platform() == 'Windows' else ''
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
			}
		}
		if platform() == 'Windows':
			home_dir = r'C:\Users\michael'
		else:
			home_dir = '/Users/michael'
		self.file_system = StubFileSystem(files, home_dir=home_dir)
		self.instance = SuggestLocations(recent_locations, self.file_system)
	def _check_query_returns(self, query, paths, highlights=None):
		query = self._replace_pathsep(query)
		paths = tuple(map(self._replace_pathsep, paths))
		if highlights is None:
			highlights = (self._full_range(query),) * len(paths)
		actual_paths, actual_highlights = unzip(self.instance(query))
		self.assertEqual(paths, actual_paths)
		self.assertEqual(highlights, actual_highlights)
	def _replace_pathsep(self, path):
		return path.replace('/', os.sep)
	def _full_range(self, string):
		return list(range(len(string)))

def unzip(lst):
	return zip(*lst)

class StubFileSystem:
	def __init__(self, files, home_dir):
		self.files = files
		self.home_dir = home_dir
	def isdir(self, path):
		try:
			self._get_dir(path)
		except KeyError:
			return False
		return True
	def _get_dir(self, path):
		if not path:
			raise KeyError(path)
		parts = normpath(path).split(os.sep)
		curr = self.files
		for part in parts:
			curr = curr[part]
		return curr
	def expanduser(self, path):
		return path.replace('~', self.home_dir)
	def listdir(self, path):
		return sorted(list(self._get_dir(path)))