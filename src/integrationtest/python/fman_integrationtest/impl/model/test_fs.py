from fman.impl.model.fs import ZipFileSystem
from fman.url import as_url, join, as_human_readable
from fman_integrationtest import get_resource
from pathlib import Path
from shutil import copyfile
from tempfile import TemporaryDirectory
from unittest import TestCase
from zipfile import ZipFile

import os
import os.path

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
					'zip://' + self._path('nonexistent'), as_url(tmp_dir)
				)
	def test_add_file(self):
		with TemporaryDirectory() as tmp_dir:
			file_to_add = os.path.join(tmp_dir, 'tmp.txt')
			file_contents = 'added!'
			with open(file_to_add, 'w') as f:
				f.write(file_contents)
			zip_file = copyfile(self._zip, os.path.join(tmp_dir, 'test.zip'))
			path_in_zip = ('ZipFileTest', 'Directory', 'added.txt')
			dest_url_in_zip = join(as_url(zip_file, 'zip://'), *path_in_zip)
			self._fs.copy(as_url(file_to_add), dest_url_in_zip)
			with TemporaryDirectory() as dest_dir:
				dest_url = join(as_url(dest_dir), 'extracted.txt')
				self._fs.copy(dest_url_in_zip, dest_url)
				with open(as_human_readable(dest_url)) as f:
					actual_contents = f.read()
				self.assertEqual(file_contents, actual_contents)
	def test_add_directory(self):
		with TemporaryDirectory() as zip_contents:
			with ZipFile(self._zip) as zip_file:
				zip_file.extractall(zip_contents)
			with TemporaryDirectory() as zip_container:
				dest_zip_file = os.path.join(zip_container, 'test.zip')
				with ZipFile(dest_zip_file, 'w'):
					pass
				self._fs.copy(
					as_url(os.path.join(zip_contents, 'ZipFileTest')),
					join(as_url(dest_zip_file, 'zip://'), 'ZipFileTest')
				)
				with TemporaryDirectory() as dest_dir:
					with ZipFile(dest_zip_file) as zip_file:
						zip_file.extractall(dest_dir)
					self.assertEqual(
						self._get_zip_contents(), self._read_directory(dest_dir)
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