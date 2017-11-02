from core.fileoperations import CopyFiles, MoveFiles
from core.tests import StubUI
from fman import YES, NO, OK, YES_TO_ALL, NO_TO_ALL, ABORT, PLATFORM
from fman.url import join, dirname, as_file_url, as_human_readable
from os.path import exists
from tempfile import TemporaryDirectory
from unittest import TestCase, skipIf

import fman.fs
import os
import os.path
import stat

class FileTreeOperationAT:
	def __init__(self, operation, operation_descr_verb, methodName='runTest'):
		super().__init__(methodName=methodName)
		self.operation = operation
		self.operation_descr_verb = operation_descr_verb
	def test_single_file(self, dest_dir=None):
		if dest_dir is None:
			dest_dir = self.dest
		src_file = join(self.src, 'test.txt')
		self._touch(src_file, '1234')
		self._perform_on(src_file, dest_dir=dest_dir)
		self._expect_files({'test.txt'}, dest_dir)
		self._assert_file_contents_equal(join(dest_dir, 'test.txt'), '1234')
		return src_file
	def test_singe_file_dest_dir_does_not_exist(self):
		self.test_single_file(dest_dir=join(self.dest, 'subdir'))
	def test_empty_directory(self):
		empty_dir = join(self.src, 'test')
		self._mkdir(empty_dir)
		self._perform_on(empty_dir)
		self._expect_files({'test'})
		self._expect_files(set(), in_dir=join(self.dest, 'test'))
		return empty_dir
	def test_directory_several_files(self, dest_dir=None):
		if dest_dir is None:
			dest_dir = self.dest
		file_outside_dir = join(self.src, 'file1.txt')
		self._touch(file_outside_dir)
		dir_ = join(self.src, 'dir')
		self._mkdir(dir_)
		file_in_dir = join(dir_, 'file.txt')
		self._touch(file_in_dir)
		executable_in_dir = join(dir_, 'executable')
		self._touch(executable_in_dir, 'abc')
		if PLATFORM != 'Windows':
			st_mode = self._stat(executable_in_dir).st_mode
			self._chmod(executable_in_dir, st_mode | stat.S_IEXEC)
		self._perform_on(file_outside_dir, dir_, dest_dir=dest_dir)
		self._expect_files({'file1.txt', 'dir'}, dest_dir)
		self._expect_files({'executable', 'file.txt'}, join(dest_dir, 'dir'))
		executable_dst = join(dest_dir, 'dir', 'executable')
		self._assert_file_contents_equal(executable_dst, 'abc')
		if PLATFORM != 'Windows':
			self.assertTrue(self._stat(executable_dst).st_mode & stat.S_IEXEC)
		return [file_outside_dir, dir_]
	def test_directory_several_files_dest_dir_does_not_exist(self):
		self.test_directory_several_files(dest_dir=join(self.dest, 'subdir'))
	def test_overwrite_files(
		self, answers=(YES, YES), expect_overrides=(True, True),
		files=('a.txt', 'b.txt'), perform_on_files=None
	):
		if perform_on_files is None:
			perform_on_files = files
		src_files = [join(self.src, *relpath.split('/')) for relpath in files]
		dest_files = [join(self.dest, *relpath.split('/')) for relpath in files]
		file_contents = lambda src_file_path: os.path.basename(src_file_path)
		for i, src_file_path in enumerate(src_files):
			self._makedirs(dirname(src_file_path), exist_ok=True)
			self._touch(src_file_path, file_contents(src_file_path))
			dest_file_path = dest_files[i]
			self._makedirs(dirname(dest_file_path), exist_ok=True)
			self._touch(dest_file_path)
		for i, answer in enumerate(answers):
			file_name = os.path.basename(files[i])
			self._expect_alert(
				('%s exists. Do you want to overwrite it?' % file_name,
				 YES | NO | YES_TO_ALL | NO_TO_ALL | ABORT, YES),
				answer=answer
			)
		self._perform_on(*[join(self.src, fname) for fname in perform_on_files])
		for i, expect_override in enumerate(expect_overrides):
			dest_file = dest_files[i]
			with self._open(dest_file, 'r') as f:
				contents = f.read()
			if expect_override:
				self.assertEqual(file_contents(src_files[i]), contents)
			else:
				self.assertEqual(
					'', contents,
					'File %s was overwritten, contrary to expectations.' %
					os.path.basename(dest_file)
				)
		return src_files
	def test_overwrite_files_no_yes(self):
		self.test_overwrite_files((NO, YES), (False, True))
	def test_overwrite_files_yes_all(self):
		self.test_overwrite_files((YES_TO_ALL,), (True, True))
	def test_overwrite_files_no_all(self):
		self.test_overwrite_files((NO_TO_ALL,), (False, False))
	def test_overwrite_files_yes_no_all(self):
		self.test_overwrite_files((YES, NO_TO_ALL), (True, False))
	def test_overwrite_files_abort(self):
		self.test_overwrite_files((ABORT,), (False, False))
	def test_overwrite_files_in_directory(self):
		self.test_overwrite_files(
			files=('dir/a.txt', 'b.txt'), perform_on_files=('dir', 'b.txt')
		)
	def test_overwrite_directory_abort(self):
		self.test_overwrite_files(
			(ABORT,), (False, False), files=('dir/a.txt', 'b.txt'),
			perform_on_files=('dir', 'b.txt')
		)
	def test_move_to_self(self):
		a, b = join(self.dest, 'a'), join(self.dest, 'b')
		c = join(self.external_dir, 'c')
		dir_ = join(self.dest, 'dir')
		self._makedirs(dir_)
		files = [a, b, c]
		for file_ in files:
			self._touch(file_)
		# Expect alert only once:
		self._expect_alert(
			('You cannot %s a file to itself.' % self.operation_descr_verb,),
			answer=OK
		)
		self._perform_on(dir_, *files)
		# Should still have copied c:
		self._expect_files({'a', 'b', 'c', 'dir'})
		return c
	def test_external_file(self):
		external_file = join(self.external_dir, 'test.txt')
		self._touch(external_file)
		self._perform_on(external_file)
		self._expect_files({'test.txt'})
		return external_file
	def test_nested_dir(self):
		parent_dir = join(self.src, 'parent_dir')
		nested_dir = join(parent_dir, 'nested_dir')
		text_file = join(nested_dir, 'file.txt')
		self._makedirs(nested_dir)
		self._touch(text_file)
		self._perform_on(parent_dir)
		self._expect_files({'parent_dir'})
		self._expect_files({'nested_dir'}, join(self.dest, 'parent_dir'))
		self._expect_files(
			{'file.txt'}, join(self.dest, 'parent_dir', 'nested_dir')
		)
		return parent_dir
	def test_symlink(self):
		symlink_source = join(self.src, 'symlink_source')
		self._touch(symlink_source)
		symlink = join(self.src, 'symlink')
		self._symlink(symlink_source, symlink)
		self._perform_on(symlink)
		self._expect_files({'symlink'})
		symlink_dest = join(self.dest, 'symlink')
		self.assertTrue(self._islink(symlink_dest))
		symlink_dest_source = self._readlink(symlink_dest)
		self.assertTrue(fman.fs.samefile(symlink_source, symlink_dest_source))
		return symlink
	def test_dest_name(self, src_equals_dest=False, preserves_files=True):
		src_dir = self.dest if src_equals_dest else self.src
		foo = join(src_dir, 'foo')
		self._touch(foo, '1234')
		self._perform_on(foo, dest_name='bar')
		expected_files = {'bar'}
		if preserves_files and src_equals_dest:
			expected_files.add('foo')
		self._expect_files(expected_files)
		self._assert_file_contents_equal(join(self.dest, 'bar'), '1234')
		return foo
	def test_dest_name_same_dir(self):
		self.test_dest_name(src_equals_dest=True)
	def test_error_continue(self, do_continue=True):
		nonexistent_file = join(self.src, 'foo.txt')
		existent_file = join(self.src, 'bar.txt')
		self._touch(existent_file)
		self._expect_alert(
			('Could not %s %s. Do you want to continue?' %
			 (self.operation_descr_verb, nonexistent_file),
			 YES | YES_TO_ALL | ABORT, YES), answer=YES if do_continue else ABORT
		)
		self._perform_on(nonexistent_file, existent_file)
		self._expect_files({'bar.txt'} if do_continue else set())
	def test_error_abort(self):
		self.test_error_continue(do_continue=False)
	def test_relative_path_parent_dir(self):
		src_file = join(self.src, 'test.txt')
		self._touch(src_file, '1234')
		self._perform_on(src_file, dest_dir='..')
		dest_dir_abs = dirname(self.src)
		self._expect_files({'src', 'test.txt'}, dest_dir_abs)
		self._assert_file_contents_equal(join(dest_dir_abs, 'test.txt'), '1234')
	def test_relative_path_subdir(self):
		src_file = join(self.src, 'test.txt')
		self._touch(src_file, '1234')
		subdir = join(self.src, 'subdir')
		self._makedirs(subdir, exist_ok=True)
		self._perform_on(src_file, dest_dir='subdir')
		self._expect_files({'test.txt'}, subdir)
		self._assert_file_contents_equal(join(subdir, 'test.txt'), '1234')
	def setUp(self):
		super().setUp()
		self.ui = StubUI(self)
		self._tmp_dir = TemporaryDirectory()
		self._root = as_file_url(self._tmp_dir.name)
		# We need intermediate 'src-parent' for test_relative_path_parent_dir:
		self.src = join(self._root, 'src-parent', 'src')
		self._makedirs(self.src)
		self.dest = join(self._root, 'dest')
		self._makedirs(self.dest)
		self.external_dir = join(self._root, 'external-dir')
		self._makedirs(self.external_dir)
		# Create a dummy file to test that not _all_ files are copied from src:
		self._touch(join(self.src, 'dummy'))
	def tearDown(self):
		self._tmp_dir.cleanup()
		super().tearDown()
	def _perform_on(self, *files, dest_dir=None, dest_name=None):
		if dest_dir is None:
			dest_dir = self.dest
		self.operation(self.ui, files, dest_dir, self.src, dest_name)()
		self.ui.verify_expected_dialogs_were_shown()
	def _assert_file_contents_equal(self, url, expected_contents):
		with self._open(url, 'r') as f:
			self.assertEqual(expected_contents, f.read())
	def _touch(self, file_url, contents=None):
		self._makedirs(dirname(file_url), exist_ok=True)
		fman.fs.touch(file_url)
		if contents is not None:
			with self._open(file_url, 'w') as f:
				f.write(contents)
	def _mkdir(self, dir_url):
		fman.fs.mkdir(dir_url)
	def _makedirs(self, dir_url, exist_ok=False):
		fman.fs.makedirs(dir_url, exist_ok=exist_ok)
	def _open(self, file_url, mode):
		return open(as_human_readable(file_url), mode)
	def _stat(self, file_url):
		return os.stat(as_human_readable(file_url))
	def _chmod(self, file_url, mode):
		return os.chmod(as_human_readable(file_url), mode)
	def _symlink(self, src_url, dst_url):
		os.symlink(as_human_readable(src_url), as_human_readable(dst_url))
	def _islink(self, file_url):
		return os.path.islink(as_human_readable(file_url))
	def _readlink(self, link_url):
		return as_file_url(os.readlink(as_human_readable(link_url)))
	def _expect_alert(self, args, answer):
		self.ui.expect_alert(args, answer)
	def _expect_files(self, files, in_dir=None):
		if in_dir is None:
			in_dir = self.dest
		self.assertEqual(files, set(fman.fs.listdir(in_dir)))

try:
	from os import geteuid
except ImportError:
	_is_root = False
else:
	_is_root = geteuid() == 0

class CopyFilesTest(FileTreeOperationAT, TestCase):
	def __init__(self, methodName='runTest'):
		super().__init__(CopyFiles, 'copy', methodName)
	@skipIf(_is_root, 'Skip this test when run by root')
	def test_overwrite_locked_file(self):
		# Would also like to have this as a test case in MoveFilesTest but the
		# call to chmod(0o444) which we use to lock the file doesn't prevent the
		# file from being overwritten by a move. Another solution would be to
		# chown the file as a different user, but then the test would require
		# root privileges. So keep it here only for now.
		dir_ = join(self.src, 'dir')
		fman.fs.makedirs(dir_)
		src_file = join(dir_, 'foo.txt')
		self._touch(src_file, 'dstn')
		dest_dir = join(self.dest, 'dir')
		fman.fs.makedirs(dest_dir)
		locked_dest_file = join(dest_dir, 'foo.txt')
		self._touch(locked_dest_file)
		self._chmod(locked_dest_file, 0o444)
		try:
			self._expect_alert(
				('foo.txt exists. Do you want to overwrite it?',
				 YES | NO | YES_TO_ALL | NO_TO_ALL | ABORT, YES), answer=YES
			)
			self._expect_alert(
				('Could not copy %s. Do you want to continue?' % src_file,
				 YES | YES_TO_ALL | ABORT, YES), answer=YES
			)
			self._perform_on(dir_)
		finally:
			# Make the file writeable again because on Windows, the temp dir
			# containing it can't be cleaned up otherwise.
			self._chmod(locked_dest_file, 0o777)

class MoveFilesTest(FileTreeOperationAT, TestCase):
	def __init__(self, methodName='runTest'):
		super().__init__(MoveFiles, 'move', methodName)
	def test_single_file(self, dest_dir=None):
		src_file = super().test_single_file(dest_dir)
		self.assertFalse(exists(src_file))
	def test_empty_directory(self):
		empty_dir_src = super().test_empty_directory()
		self.assertFalse(exists(empty_dir_src))
	def test_directory_several_files(self, dest_dir=None):
		src_files = super().test_directory_several_files(dest_dir=dest_dir)
		for file_ in src_files:
			self.assertFalse(exists(file_))
	def test_overwrite_files(
		self, answers=(YES, YES), expect_overrides=(True, True),
		files=('a.txt', 'b.txt'), perform_on_files=None
	):
		src_files = super().test_overwrite_files(
			answers, expect_overrides, files, perform_on_files
		)
		for i, file_ in enumerate(src_files):
			if expect_overrides[i]:
				self.assertFalse(exists(file_), file_)
	def test_move_to_self(self):
		external_file = super().test_move_to_self()
		self.assertFalse(exists(external_file))
	def test_external_file(self):
		external_file = super().test_external_file()
		self.assertFalse(exists(external_file))
	def test_nested_dir(self):
		parent_dir = super().test_nested_dir()
		self.assertFalse(exists(parent_dir))
	def test_symlink(self):
		symlink = super().test_symlink()
		self.assertFalse(exists(symlink))
	def test_dest_name(self, src_equals_dest=False):
		super().test_dest_name(src_equals_dest, preserves_files=False)
	def test_overwrite_dir_skip_file(self):
		src_dir = join(self.src, 'dir')
		self._makedirs(src_dir)
		src_file = join(src_dir, 'test.txt')
		self._touch(src_file, 'src contents')
		dest_dir = join(self.dest, 'dir')
		self._makedirs(dest_dir)
		dest_file = join(dest_dir, 'test.txt')
		self._touch(dest_file, 'dest contents')
		self._expect_alert(
			('test.txt exists. Do you want to overwrite it?',
			 YES | NO | YES_TO_ALL | NO_TO_ALL | ABORT, YES),
			answer=NO
		)
		self._perform_on(src_dir)
		self.assertTrue(
			fman.fs.exists(src_file),
			"Source file was skipped and should not have been deleted."
		)
		self._assert_file_contents_equal(src_file, 'src contents')
		self._assert_file_contents_equal(dest_file, 'dest contents')