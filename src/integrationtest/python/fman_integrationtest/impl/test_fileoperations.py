from fman.impl.fileoperations import CopyFiles, FileOperation, Yes, No, Ok, \
	YesToAll, NoToAll, Abort, MoveFiles
from os import listdir, mkdir, chmod, makedirs, readlink
from os.path import basename, join, dirname, exists, islink, realpath, samefile
from tempfile import TemporaryDirectory
from unittest import TestCase

import os
import stat

class FileTreeOperationAT(TestCase):
	def __init__(self, operation, operation_descr_verb, methodName='runTest'):
		super().__init__(methodName=methodName)
		self.operation = operation
		self.operation_descr_verb = operation_descr_verb
	def test_single_file(self):
		src_file = join(self.src, 'test.txt')
		with open(src_file, 'w') as f:
			f.write('1234')
		self._perform_on(src_file)
		self.assertEquals(['test.txt'], listdir(self.dest))
		with open(join(self.dest, 'test.txt'), 'r') as f:
			self.assertEquals('1234', f.read())
		return src_file
	def test_empty_directory(self):
		empty_dir = join(self.src, 'test')
		mkdir(empty_dir)
		self._perform_on(empty_dir)
		self.assertEquals(['test'], listdir(self.dest))
		self.assertEquals([], listdir(join(self.dest, 'test')))
		return empty_dir
	def test_directory_several_files(self):
		file_outside_dir = join(self.src, 'file1.txt')
		self._touch(file_outside_dir)
		dir_ = join(self.src, 'dir')
		mkdir(dir_)
		file_in_dir = join(dir_, 'file.txt')
		self._touch(file_in_dir)
		executable_in_dir = join(dir_, 'executable')
		with open(executable_in_dir, 'w') as f:
			f.write('abc')
		st_mode = os.stat(executable_in_dir).st_mode
		chmod(executable_in_dir, st_mode | stat.S_IEXEC)
		self._perform_on(file_outside_dir, dir_)
		self.assertEquals({'file1.txt', 'dir'}, set(listdir(self.dest)))
		self.assertEquals(
			{'executable', 'file.txt'}, set(listdir(join(self.dest, 'dir')))
		)
		executable_dst = join(self.dest, 'dir', 'executable')
		with open(executable_dst, 'r') as f:
			self.assertEquals('abc', f.read())
		self.assertTrue(os.stat(executable_dst).st_mode & stat.S_IEXEC)
		return [file_outside_dir, dir_]
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
			with open(src_file_path, 'w') as f:
				f.write(file_contents(src_file_path))
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
				self.assertEquals(file_contents(src_files[i]), contents)
			else:
				self.assertEquals(
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
		self.assertEquals({'a', 'b', 'c', 'dir'}, set(listdir(self.dest)))
		return c
	def test_external_file(self):
		external_file = join(self.external_dir, 'test.txt')
		self._touch(external_file)
		self._perform_on(external_file)
		self.assertEquals(['test.txt'], listdir(self.dest))
		return external_file
	def test_nested_dir(self):
		parent_dir = join(self.src, 'parent_dir')
		nested_dir = join(parent_dir, 'nested_dir')
		text_file = join(nested_dir, 'file.txt')
		makedirs(nested_dir)
		self._touch(text_file)
		self._perform_on(parent_dir)
		self.assertEquals(['parent_dir'], listdir(self.dest))
		self.assertEquals(
			['nested_dir'], listdir(join(self.dest, 'parent_dir'))
		)
		self.assertEquals(
			['file.txt'], listdir(join(self.dest, 'parent_dir', 'nested_dir'))
		)
		return parent_dir
	def test_symlink(self):
		symlink_source = join(self.src, 'symlink_source')
		self._touch(symlink_source)
		symlink = join(self.src, 'symlink')
		os.symlink(symlink_source, symlink)
		self._perform_on(symlink)
		self.assertEquals(['symlink'], listdir(self.dest))
		symlink_dest = join(self.dest, 'symlink')
		self.assertTrue(islink(symlink_dest))
		symlink_dest_source = realpath(readlink(symlink_dest))
		self.assertTrue(samefile(symlink_source, symlink_dest_source))
		return symlink
	def setUp(self):
		self.gui_thread = StubGuiThread(self)
		self._src = TemporaryDirectory()
		self._dest = TemporaryDirectory()
		self._external_dir = TemporaryDirectory()
		# Create a dummy file to test that not _all_ files are copied from src:
		self._touch(join(self.src, 'dummy'))
	def _perform_on(self, *files):
		self.operation(self.gui_thread, files, self.dest, self.src)()
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
		self._src.cleanup()
		self._dest.cleanup()
	def _assert_contents_are_equal(self, f1, f2):
		with open(f1, 'r') as f:
			contents_1 = f.read()
		with open(f2, 'r') as f:
			contents_2 = f.read()
		self.assertEquals(contents_1, contents_2)
	def _touch(self, file_path):
		with open(file_path, 'w'):
			pass
	def _expect_prompt(self, args, answer):
		self.gui_thread.expect_prompt(args, answer)

class CopyFilesTest(FileTreeOperationAT):
	def __init__(self, methodName='runTest'):
		super().__init__(CopyFiles, 'copy', methodName)

class MoveFilesTest(FileTreeOperationAT):
	def __init__(self, methodName='runTest'):
		super().__init__(MoveFiles, 'move', methodName)
	def test_single_file(self):
		src_file = super().test_single_file()
		self.assertFalse(exists(src_file))
	def test_empty_directory(self):
		empty_dir_src = super().test_empty_directory()
		self.assertFalse(exists(empty_dir_src))
	def test_directory_several_files(self):
		src_files = super().test_directory_several_files()
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

class StubGuiThread:
	def __init__(self, test_case):
		self.expected_prompts = []
		self.test_case = test_case
	def execute(self, fn, *args, **kwargs):
		if fn.__func__ == FileOperation._show_message_box:
			if not self.expected_prompts:
				self.test_case.fail('Unexpected prompt: %r' % args[0])
				return
			expected_args, answer = self.expected_prompts.pop(0)
			self.test_case.assertEquals(expected_args, args)
			return answer
		raise ValueError('Unexpected method call: %r' % fn)
	def expect_prompt(self, args, answer):
		self.expected_prompts.append((args, answer))
	def verify_expected_prompts_were_shown(self):
		self.test_case.assertEquals([], self.expected_prompts)