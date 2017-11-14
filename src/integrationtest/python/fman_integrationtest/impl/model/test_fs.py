from errno import ENOENT
from fman.impl.model.fs import ZipFileSystem
from fman.url import as_url, join, as_human_readable, splitscheme
from fman_integrationtest import get_resource
from os import listdir
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
		self._test_extract_dir('')
	def _test_extract_dir(self, path_in_zip):
		expected_files = self._get_zip_contents()
		if path_in_zip:
			for part in path_in_zip.split('/'):
				expected_files = expected_files[part]
		with TemporaryDirectory() as tmp_dir:
			# Create a subdirectory because the destination directory of a copy
			# operation must not yet exist:
			dst_dir = os.path.join(tmp_dir, 'dest')
			self._fs.copy(self._url(path_in_zip), as_url(dst_dir))
			self.assertEqual(expected_files, self._read_directory(dst_dir))
	def test_extract_subdir(self):
		self._test_extract_dir('ZipFileTest/Directory')
	def test_extract_empty_directory(self):
		self._test_extract_dir('ZipFileTest/Empty directory')
	def test_extract_file(self):
		with TemporaryDirectory() as tmp_dir:
			self._fs.copy(
				self._url('ZipFileTest/file.txt'),
				join(as_url(tmp_dir), 'file.txt')
			)
			self.assertEqual(['file.txt'], listdir(tmp_dir))
			with open(os.path.join(tmp_dir, 'file.txt')) as f:
				self.assertEqual(
					self._get_zip_contents()['ZipFileTest']['file.txt'],
					f.read()
				)
	def test_extract_nonexistent(self):
		with self.assertRaises(FileNotFoundError):
			with TemporaryDirectory() as tmp_dir:
				self._fs.copy(self._url('nonexistent'), as_url(tmp_dir))
	def test_add_file(self):
		with TemporaryDirectory() as tmp_dir:
			file_to_add = os.path.join(tmp_dir, 'tmp.txt')
			file_contents = 'added!'
			with open(file_to_add, 'w') as f:
				f.write(file_contents)
			dest_url_in_zip = self._url('ZipFileTest/Directory/added.txt')
			self._fs.copy(as_url(file_to_add), dest_url_in_zip)
			dest_url = join(as_url(tmp_dir), 'extracted.txt')
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
	def test_delete_file(self):
		self._test_delete('ZipFileTest/Directory/Subdirectory/file 3.txt')
	def _test_delete(self, path_in_zip):
		expected_contents = self._get_zip_contents()
		self._pop_from_dir_dict(expected_contents, path_in_zip)
		self._fs.delete(self._path(path_in_zip))
		self.assertEqual(expected_contents, self._get_zip_contents())
	def test_delete_directory(self):
		self._test_delete('ZipFileTest/Directory')
	def test_delete_empty_directory(self):
		self._test_delete('ZipFileTest/Empty directory')
	def test_delete_main_directory(self):
		self._test_delete('ZipFileTest')
	def test_delete_nonexistent(self):
		with self.assertRaises(FileNotFoundError):
			self._fs.delete(self._path('nonexistent'))
	def test_move_file_out_of_archive(self):
		file_path = 'ZipFileTest/Directory/Subdirectory/file 3.txt'
		expected_zip_contents = self._get_zip_contents()
		removed = self._pop_from_dir_dict(expected_zip_contents, file_path)
		with TemporaryDirectory() as tmp_dir:
			dst = os.path.join(tmp_dir, 'test.tzt')
			self._fs.move(self._url(file_path), as_url(dst))
			self.assertEqual(expected_zip_contents, self._get_zip_contents())
			with open(dst) as f:
				self.assertEqual(removed, f.read())
	def test_move_dir_out_of_archive(self):
		self._test_move_dir_out_of_archive('ZipFileTest/Directory')
	def test_move_empty_dir_out_of_archive(self):
		self._test_move_dir_out_of_archive('ZipFileTest/Empty directory')
	def test_move_main_dir_out_of_archive(self):
		self._test_move_dir_out_of_archive('ZipFileTest')
	def _test_move_dir_out_of_archive(self, path_in_zip):
		expected_zip_contents = self._get_zip_contents()
		removed = self._pop_from_dir_dict(expected_zip_contents, path_in_zip)
		with TemporaryDirectory() as tmp_dir:
			dst_dir = os.path.join(tmp_dir, 'dest')
			self._fs.move(self._url(path_in_zip), as_url(dst_dir))
			self.assertEqual(expected_zip_contents, self._get_zip_contents())
			self.assertEqual(removed, self._read_directory(dst_dir))
	def test_move_file_into_archive(self):
		expected_zip_contents = self._get_zip_contents()
		with TemporaryDirectory() as tmp_dir:
			file_path = os.path.join(tmp_dir, 'test.txt')
			with open(file_path, 'w') as f:
				f.write('success!')
			dst_url = self._url('test_dest.txt')
			self._fs.move(as_url(file_path), dst_url)
			self.assertFalse(Path(file_path).exists())
			expected_zip_contents['test_dest.txt'] = 'success!'
			self.assertEqual(expected_zip_contents, self._get_zip_contents())
	def test_rename_directory(self):
		expected_zip_contents = self._get_zip_contents()
		expected_zip_contents['Destination'] = \
			expected_zip_contents['ZipFileTest'].pop('Directory')
		self._fs.move(
			self._url('ZipFileTest/Directory'), self._url('Destination')
		)
		self.assertEqual(expected_zip_contents, self._get_zip_contents())
	def test_rename_file(self):
		expected_zip_contents = self._get_zip_contents()
		src_path = 'ZipFileTest/Directory/Subdirectory/file 3.txt'
		expected_zip_contents['ZipFileTest']['Directory']['destination.txt'] = \
			self._pop_from_dir_dict(expected_zip_contents, src_path)
		self._fs.move(
			self._url(src_path),
			self._url('ZipFileTest/Directory/destination.txt')
		)
		self.assertEqual(expected_zip_contents, self._get_zip_contents())
	def test_move_file_between_archives(self):
		src_path = 'ZipFileTest/Directory/Subdirectory/file 3.txt'
		expected_zip_contents = self._get_zip_contents()
		src_contents = self._pop_from_dir_dict(expected_zip_contents, src_path)
		with TemporaryDirectory() as dst_dir:
			dst_zip = os.path.join(dst_dir, 'dest.zip')
			# Give the Zip file some contents:
			dummy_txt = os.path.join(dst_dir, 'dummy.txt')
			dummy_contents = 'some contents'
			with open(dummy_txt, 'w') as f:
				f.write(dummy_contents)
			with ZipFile(dst_zip, 'w') as zip_file:
				zip_file.write(dummy_txt, 'dummy.txt')
			self._fs.move(
				self._url(src_path), join(as_url(dst_zip, 'zip://'), 'dest.txt')
			)
			self.assertEqual(expected_zip_contents, self._get_zip_contents())
			self.assertEqual(
				{'dummy.txt': dummy_contents, 'dest.txt': src_contents},
				self._get_zip_contents(dst_zip)
			)
	def _expect_iterdir_result(self, path_in_zip, expected_contents):
		full_path = self._path(path_in_zip)
		self.assertEqual(expected_contents, set(self._fs.iterdir(full_path)))
	def _url(self, path_in_zip):
		return as_url(self._path(path_in_zip), 'zip://')
	def _path(self, path_in_zip):
		return self._zip.replace(os.sep, '/') + \
			   ('/' if path_in_zip else '') + \
			   path_in_zip
	def _get_zip_contents(self, zip_path=None):
		if zip_path is None:
			zip_path = self._zip
		with TemporaryDirectory() as tmp_dir:
			with ZipFile(zip_path) as zip_file:
				zip_file.extractall(tmp_dir)
			return self._read_directory(tmp_dir)
	def _pop_from_dir_dict(self, dir_dict, path):
		parts = path.split('/')
		for part in parts[:-1]:
			dir_dict = dir_dict[part]
		return dir_dict.pop(parts[-1])
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
		super().setUp()
		self._fs = ZipFileSystem()
		self._tmp_dir = TemporaryDirectory()
		self._zip = copyfile(
			get_resource('ZipFileSystemTest.zip'),
			os.path.join(self._tmp_dir.name, 'ZipFileSystemTest.zip')
		)
		self._dirs_in_zip = (
			'', 'ZipFileTest', 'ZipFileTest/Directory',
			'ZipFileTest/Directory/Subdirectory', 'ZipFileTest/Empty directory'
		)
		self._files_in_zip = (
			'ZipFileTest/file.txt', 'ZipFileTest/Directory/file 2.txt',
			'ZipFileTest/Directory/Subdirectory/file 3.txt'
		)
		self.maxDiff = None
	def tearDown(self):
		self._tmp_dir.cleanup()
		super().tearDown()