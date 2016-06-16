from fman.impl import fileoperations
from fman.impl.fileoperations import CopyFiles, Yes, No, Ok, YesToAll, \
	NoToAll, Abort, MoveFiles
from fman.impl.gui_operations import show_message_box
from fman.util import system
from os import listdir, mkdir, chmod, makedirs, readlink
from os.path import basename, join, dirname, exists, islink, realpath, samefile
from tempfile import TemporaryDirectory
from unittest import TestCase

import logging
import os
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
		self.assertEqual(['test.txt'], listdir(dest_dir))
		with open(join(dest_dir, 'test.txt'), 'r') as f:
			self.assertEqual('1234', f.read())
		return src_file
	def test_singe_file_dest_dir_does_not_exist(self):
		self.test_single_file(dest_dir=join(self.dest, 'subdir'))
	def test_empty_directory(self):
		empty_dir = join(self.src, 'test')
		mkdir(empty_dir)
		self._perform_on(empty_dir)
		self.assertEqual(['test'], listdir(self.dest))
		self.assertEqual([], listdir(join(self.dest, 'test')))
		return empty_dir
	def test_directory_several_files(self, dest_dir=None):
		if dest_dir is None:
			dest_dir = self.dest
		file_outside_dir = join(self.src, 'file1.txt')
		self._touch(file_outside_dir)
		dir_ = join(self.src, 'dir')
		mkdir(dir_)
		file_in_dir = join(dir_, 'file.txt')
		self._touch(file_in_dir)
		executable_in_dir = join(dir_, 'executable')
		self._touch(executable_in_dir, 'abc')
		if not system.is_windows():
			st_mode = os.stat(executable_in_dir).st_mode
			chmod(executable_in_dir, st_mode | stat.S_IEXEC)
		self._perform_on(file_outside_dir, dir_, dest_dir=dest_dir)
		self.assertEqual({'file1.txt', 'dir'}, set(listdir(dest_dir)))
		self.assertEqual(
			{'executable', 'file.txt'}, set(listdir(join(dest_dir, 'dir')))
		)
		executable_dst = join(dest_dir, 'dir', 'executable')
		with open(executable_dst, 'r') as f:
			self.assertEqual('abc', f.read())
		if not system.is_windows():
			self.assertTrue(os.stat(executable_dst).st_mode & stat.S_IEXEC)
		return [file_outside_dir, dir_]
	def test_directory_several_files_dest_dir_does_not_exist(self):
		self.test_directory_several_files(dest_dir=join(self.dest, 'subdir'))
	def test_overwrite_files(
		self, answers=(Yes, Yes), expect_overrides=(True, True),
		files=('a.txt', 'b.txt'), perform_on_files=None
	):
		if perform_on_files is None:
			perform_on_files = files
		src_files = [join(self.src, *relpath.split('/')) for relpath in files]
		dest_files = [join(self.dest, *relpath.split('/')) for relpath in files]
		file_contents = lambda src_file_path: basename(src_file_path)
		for i, src_file_path in enumerate(src_files):
			makedirs(dirname(src_file_path), exist_ok=True)
			self._touch(src_file_path, file_contents(src_file_path))
			dest_file_path = dest_files[i]
			makedirs(dirname(dest_file_path), exist_ok=True)
			self._touch(dest_file_path)
		for i, answer in enumerate(answers):
			file_name = basename(files[i])
			self._expect_prompt(
				('%s exists. Do you want to override it?' % file_name,
				 Yes | No | YesToAll | NoToAll | Abort, Yes),
				answer=answer
			)
		self._perform_on(*[join(self.src, fname) for fname in perform_on_files])
		for i, expect_override in enumerate(expect_overrides):
			dest_file = dest_files[i]
			with open(dest_file, 'r') as f:
				contents = f.read()
			if expect_override:
				self.assertEqual(file_contents(src_files[i]), contents)
			else:
				self.assertEqual(
					'', contents,
					'File %s was overwritten, contrary to expectations.' %
					basename(dest_file)
				)
		return src_files
	def test_overwrite_files_no_yes(self):
		self.test_overwrite_files((No, Yes), (False, True))
	def test_overwrite_files_yes_all(self):
		self.test_overwrite_files((YesToAll,), (True, True))
	def test_overwrite_files_no_all(self):
		self.test_overwrite_files((NoToAll,), (False, False))
	def test_overwrite_files_yes_no_all(self):
		self.test_overwrite_files((Yes, NoToAll), (True, False))
	def test_overwrite_files_abort(self):
		self.test_overwrite_files((Abort,), (False, False))
	def test_overwrite_files_in_directory(self):
		self.test_overwrite_files(
			files=('dir/a.txt', 'b.txt'), perform_on_files=('dir', 'b.txt')
		)
	def test_overwrite_directory_abort(self):
		self.test_overwrite_files(
			(Abort,), (False, False), files=('dir/a.txt', 'b.txt'),
			perform_on_files=('dir', 'b.txt')
		)
	def test_move_to_self(self):
		a, b = join(self.dest, 'a'), join(self.dest, 'b')
		c = join(self.external_dir, 'c')
		dir_ = join(self.dest, 'dir')
		makedirs(dir_)
		files = [a, b, c]
		for file_ in files:
			self._touch(file_)
		# Expect prompt only once:
		self._expect_prompt(
			('You cannot %s a file to itself.' % self.operation_descr_verb,
			 Ok, Ok), answer=Ok
		)
		self._perform_on(dir_, *files)
		# Should still have copied c:
		self.assertEqual({'a', 'b', 'c', 'dir'}, set(listdir(self.dest)))
		return c
	def test_external_file(self):
		external_file = join(self.external_dir, 'test.txt')
		self._touch(external_file)
		self._perform_on(external_file)
		self.assertEqual(['test.txt'], listdir(self.dest))
		return external_file
	def test_nested_dir(self):
		parent_dir = join(self.src, 'parent_dir')
		nested_dir = join(parent_dir, 'nested_dir')
		text_file = join(nested_dir, 'file.txt')
		makedirs(nested_dir)
		self._touch(text_file)
		self._perform_on(parent_dir)
		self.assertEqual(['parent_dir'], listdir(self.dest))
		self.assertEqual(
			['nested_dir'], listdir(join(self.dest, 'parent_dir'))
		)
		self.assertEqual(
			['file.txt'], listdir(join(self.dest, 'parent_dir', 'nested_dir'))
		)
		return parent_dir
	def test_symlink(self):
		symlink_source = join(self.src, 'symlink_source')
		self._touch(symlink_source)
		symlink = join(self.src, 'symlink')
		os.symlink(symlink_source, symlink)
		self._perform_on(symlink)
		self.assertEqual(['symlink'], listdir(self.dest))
		symlink_dest = join(self.dest, 'symlink')
		self.assertTrue(islink(symlink_dest))
		symlink_dest_source = realpath(readlink(symlink_dest))
		self.assertTrue(samefile(symlink_source, symlink_dest_source))
		return symlink
	def test_dest_name(self, src_equals_dest=False, preserves_files=True):
		src_dir = self.dest if src_equals_dest else self.src
		foo = join(src_dir, 'foo')
		self._touch(foo, '1234')
		self._perform_on(foo, dest_name='bar')
		expected_files = {'bar'}
		if preserves_files and src_equals_dest:
			expected_files.add('foo')
		self.assertEqual(expected_files, set(listdir(self.dest)))
		with open(join(self.dest, 'bar'), 'r') as f:
			self.assertEqual('1234', f.read())
		return foo
	def test_dest_name_same_dir(self):
		self.test_dest_name(src_equals_dest=True)
	def test_error_continue(self, do_continue=True):
		nonexistent_file = join(self.src, 'foo.txt')
		existent_file = join(self.src, 'bar.txt')
		self._touch(existent_file)
		self._expect_prompt(
			('Could not %s %s. Do you want to continue?' %
			 (self.operation_descr_verb, nonexistent_file),
			 Yes | YesToAll | Abort, Yes), answer=Yes if do_continue else Abort
		)
		self._perform_on(nonexistent_file, existent_file)
		self.assertEqual(['bar.txt'] if do_continue else [], listdir(self.dest))
	def test_error_abort(self):
		self.test_error_continue(do_continue=False)
	def setUp(self):
		self.gui_thread = StubGuiThread(self)
		self.status_bar = StubStatusBar()
		self._src = TemporaryDirectory()
		self._dest = TemporaryDirectory()
		self._external_dir = TemporaryDirectory()
		# Create a dummy file to test that not _all_ files are copied from src:
		self._touch(join(self.src, 'dummy'))
		self._log_level_before = fileoperations._LOG.getEffectiveLevel()
		# Suppress log messages on console when running tests:
		fileoperations._LOG.setLevel(logging.CRITICAL)
	def _perform_on(self, *files, dest_dir=None, dest_name=None):
		if dest_dir is None:
			dest_dir = self.dest
		self.operation(
			self.gui_thread, self.status_bar, files, dest_dir, self.src,
			dest_name
		)()
		self.gui_thread.verify_expected_prompts_were_shown()
	@property
	def src(self):
		return self._src.name
	@property
	def dest(self):
		return self._dest.name
	@property
	def external_dir(self):
		return self._external_dir.name
	def tearDown(self):
		fileoperations._LOG.setLevel(self._log_level_before)
		self._src.cleanup()
		self._dest.cleanup()
		self._external_dir.cleanup()
	def _touch(self, file_path, contents=None):
		with open(file_path, 'w') as f:
			if contents:
				f.write(contents)
	def _expect_prompt(self, args, answer):
		self.gui_thread.expect_prompt(args, answer)

class CopyFilesTest(FileTreeOperationAT, TestCase):
	def __init__(self, methodName='runTest'):
		super().__init__(CopyFiles, 'copy', methodName)
	def test_overwrite_locked_file(self):
		# Would also like to have this as a test case in MoveFilesTest but the
		# call to chmod(0o444) which we use to lock the file doesn't prevent the
		# file from being overwritten by a move. Another solution would be to
		# chown the file as a different user, but then the test would require
		# root privileges. So keep it here only for now.
		dir_ = join(self.src, 'dir')
		makedirs(dir_)
		src_file = join(dir_, 'foo.txt')
		self._touch(src_file, 'dstn')
		dest_dir = join(self.dest, 'dir')
		makedirs(dest_dir)
		locked_dest_file = join(dest_dir, 'foo.txt')
		self._touch(locked_dest_file)
		chmod(locked_dest_file, 0o444)
		try:
			self._expect_prompt(
				('foo.txt exists. Do you want to override it?',
				 Yes | No | YesToAll | NoToAll | Abort, Yes), answer=Yes
			)
			self._expect_prompt(
				('Could not copy %s. Do you want to continue?' % src_file,
				 Yes | YesToAll | Abort, Yes), answer=Yes
			)
			self._perform_on(dir_)
		finally:
			# Make the file writeable again because on Windows, the temp dir
			# containing it can't be cleaned up otherwise.
			chmod(locked_dest_file, 0o777)

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
		self, answers=(Yes, Yes), expect_overrides=(True, True),
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

class StubGuiThread:
	def __init__(self, test_case):
		self.expected_prompts = []
		self.test_case = test_case
	def execute(self, fn, *args, **kwargs):
		if fn == show_message_box:
			if not self.expected_prompts:
				self.test_case.fail('Unexpected prompt: %r' % args[0])
				return
			expected_args, answer = self.expected_prompts.pop(0)
			self.test_case.assertEqual(expected_args, args)
			return answer
		elif fn.__func__ == StubStatusBar.showMessage:
			return
		raise ValueError('Unexpected function call: %r' % fn)
	def expect_prompt(self, args, answer):
		self.expected_prompts.append((args, answer))
	def verify_expected_prompts_were_shown(self):
		self.test_case.assertEqual(
			[], self.expected_prompts, 'Did not receive all expected prompts.'
		)

class StubStatusBar:
	def showMessage(self, _):
		pass