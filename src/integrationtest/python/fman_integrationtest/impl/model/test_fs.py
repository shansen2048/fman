from errno import ENOENT
from fman.impl.model.fs import ZipFileSystem
from fman.url import as_url, join, as_human_readable, splitscheme
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
	def test_iterdir_nonexistent_zip(self):
		with self.assertRaises(FileNotFoundError):
			list(self._fs.iterdir('nonexistent.zip'))
	def test_iterdir_nonexistent_path_in_zip(self):
		with self.assertRaises(FileNotFoundError):
			list(self._fs.iterdir(self._path('nonexistent')))
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
				zip_path = os.path.join(zip_container, 'test.zip')
				self._create_empty_zip(zip_path)
				self._fs.copy(
					as_url(os.path.join(zip_contents, 'ZipFileTest')),
					join(as_url(zip_path, 'zip://'), 'ZipFileTest')
				)
				self._expect_zip_contents(self._get_zip_contents(), zip_path)
	def test_replace_file(self):
		with TemporaryDirectory() as tmp_dir:
			zip_path = os.path.join(tmp_dir, 'test.zip')
			some_file = os.path.join(tmp_dir, 'tmp.txt')
			with open(some_file, 'w') as f:
				f.write('added!')
			with ZipFile(zip_path, 'w') as zip_file:
				zip_file.write(some_file, 'tmp.txt')
			expected_contents = b'replaced!'
			with open(some_file, 'wb') as f:
				f.write(expected_contents)
			dest_url_in_zip = join(as_url(zip_path, 'zip://'), 'tmp.txt')
			self._fs.copy(as_url(some_file), dest_url_in_zip)
			with ZipFile(zip_path) as zip_file:
				# A primitive implementation would have two 'tmp.txt' entries:
				self.assertEqual(['tmp.txt'], zip_file.namelist())
				with zip_file.open('tmp.txt') as f_in_zip:
					self.assertEqual(expected_contents, f_in_zip.read())
	def test_mkdir(self):
		with TemporaryDirectory() as tmp_dir:
			zip_path = os.path.join(tmp_dir, 'test.zip')
			self._create_empty_zip(zip_path)
			self._fs.mkdir(splitscheme(as_url(zip_path, 'zip://'))[1] + '/dir')
			self._expect_zip_contents({'dir': {}}, zip_path)
	def test_mkdir_raises_fileexistserror(self):
		with TemporaryDirectory() as tmp_dir:
			zip_path = os.path.join(tmp_dir, 'test.zip')
			self._create_empty_zip(zip_path)
			dir_url_path = splitscheme(as_url(zip_path, 'zip://'))[1] + '/dir'
			self._fs.mkdir(dir_url_path)
			with self.assertRaises(FileExistsError):
				self._fs.mkdir(dir_url_path)
	def test_mkdir_raises_filenotfounderror(self):
		with TemporaryDirectory() as tmp_dir:
			zip_path = os.path.join(tmp_dir, 'test.zip')
			self._create_empty_zip(zip_path)
			zip_url_path = splitscheme(as_url(zip_path, 'zip://'))[1]
			with self.assertRaises(OSError) as cm:
				self._fs.mkdir(zip_url_path + '/nonexistent/dir')
			self.assertEqual(ENOENT, cm.exception.errno)
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
	def _expect_zip_contents(self, contents, zip_file_path):
		with TemporaryDirectory() as tmp_dir:
			with ZipFile(zip_file_path) as zip_file:
				zip_file.extractall(tmp_dir)
			self.assertEqual(contents, self._read_directory(tmp_dir))
	def _create_empty_zip(self, path):
		ZipFile(path, 'w').close()
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