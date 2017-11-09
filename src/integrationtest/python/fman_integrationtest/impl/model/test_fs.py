from fman.impl.model.fs import ZipFileSystem
from fman.url import as_url
from fman_integrationtest import get_resource
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from zipfile import ZipFile

import os

class ZipFileSystemTest(TestCase):
	def test_iterdir(self):
		self._expect_iterdir_result('', {'ZipFileTest'})
		self._expect_iterdir_result(
			'ZipFileTest', {'Directory', 'Empty directory', 'file.txt'}
		)
		self._expect_iterdir_result(
			'ZipFileTest/Directory', {'Subdirectory', 'file 2.txt'}
		)
		self._expect_iterdir_result(
			'ZipFileTest/Directory/Subdirectory', {'file 3.txt'}
		)
		self._expect_iterdir_result('ZipFileTest/Empty directory', set())
	def test_is_dir(self):
		for dir_ in self._dirs_in_zip:
			self.assertTrue(self._fs.is_dir(self._path(dir_)), dir_)
		for nondir in self._files_in_zip:
			self.assertFalse(self._fs.is_dir(self._path(nondir)), nondir)
		for nonexistent in ('nonexistent', 'ZipFileTest/nonexistent'):
			self.assertFalse(
				self._fs.is_dir(self._path(nonexistent)), nonexistent
			)
	def test_exists(self):
		for existent in self._dirs_in_zip + self._files_in_zip:
			self.assertTrue(self._fs.exists(self._path(existent)), existent)
		for nonexistent in ('nonexistent', 'ZipFileTest/nonexistent'):
			self.assertFalse(
				self._fs.exists(self._path(nonexistent)), nonexistent
			)
	def test_extract_entire_zip(self):
		self._test_extract('')
	def test_extract_subdir(self):
		self._test_extract('ZipFileTest/Directory')
	def test_extract_empty_directory(self):
		self._test_extract('ZipFileTest/Empty directory')
	def test_extract_nonexistent(self):
		with self.assertRaises(FileNotFoundError):
			with TemporaryDirectory() as tmp_dir:
				self._fs.copy(
					'zip://' + self._path('nonexistent'),
					as_url(tmp_dir)
				)
	def _test_extract(self, path_in_zip):
		expected_files = self._get_zip_contents()
		if path_in_zip:
			for part in path_in_zip.split('/'):
				expected_files = expected_files[part]
		with TemporaryDirectory() as dst_dir:
			self._fs.copy(
				'zip://' + self._path(path_in_zip), as_url(dst_dir)
			)
			self.assertEqual(expected_files, self._read_directory(dst_dir))
	def _expect_iterdir_result(self, path_in_zip, expected_contents):
		full_path = self._path(path_in_zip)
		self.assertEqual(expected_contents, set(self._fs.iterdir(full_path)))
	def _path(self, path_in_zip):
		return self._zip.replace(os.sep, '/') + \
			   ('/' if path_in_zip else '') + \
			   path_in_zip
	def _get_zip_contents(self):
		with TemporaryDirectory() as tmp_dir:
			with ZipFile(self._zip) as zipfile:
				zipfile.extractall(tmp_dir)
			return self._read_directory(tmp_dir)
	def _read_directory(self, dir_path):
		result = {}
		for child in Path(dir_path).iterdir():
			if child.is_dir():
				child_contents = self._read_directory(child)
			else:
				child_contents = child.read_text()
			result[child.name] = child_contents
		return result
	def setUp(self):
		self._fs = ZipFileSystem()
		self._zip = get_resource('ZipFileSystemTest.zip')
		self._dirs_in_zip = (
			'', 'ZipFileTest', 'ZipFileTest/Directory',
			'ZipFileTest/Directory/Subdirectory', 'ZipFileTest/Empty directory'
		)
		self._files_in_zip = (
			'ZipFileTest/file.txt', 'ZipFileTest/Directory/file 2.txt',
			'ZipFileTest/Directory/Subdirectory/file 3.txt'
		)
		self.maxDiff = None