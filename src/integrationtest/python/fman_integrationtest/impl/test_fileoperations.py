from fman.impl.fileoperations import CopyFiles, FileOperation, Yes, No, Ok, \
	YesToAll, NoToAll, Abort
from os import listdir, mkdir, chmod, makedirs
from os.path import basename, join, dirname
from shutil import copy
from tempfile import TemporaryDirectory
from unittest import TestCase

import os
import stat

class CopyFilesTest(TestCase):
	def test_copy_single_file(self):
		self._perform_copy(__file__)
		file_name = basename(__file__)
		self.assertEquals([file_name], listdir(self.dst))
		self._assert_contents_are_equal(__file__, join(self.dst, file_name))
	def test_copy_empty_directory(self):
		empty_dir = join(self.src, 'test')
		mkdir(empty_dir)
		self._perform_copy(empty_dir)
		self.assertEquals(['test'], listdir(self.dst))
	def test_copy_directory_several_files(self):
		dir_ = join(self.src, 'dir')
		mkdir(dir_)
		copy(__file__, dir_)
		executable = join(dir_, 'executable')
		with open(executable, 'w') as f:
			f.write('1234')
		chmod(executable, os.stat(executable).st_mode | stat.S_IEXEC)
		self._perform_copy(__file__, dir_)
		single_file = basename(__file__)
		self.assertEquals({single_file, 'dir'}, set(listdir(self.dst)))
		self.assertEquals(
			{'executable', single_file}, set(listdir(join(self.dst, 'dir')))
		)
		executable_dst = join(self.dst, 'dir', 'executable')
		with open(executable_dst, 'r') as f:
			self.assertEquals('1234', f.read())
		self.assertTrue(os.stat(executable_dst).st_mode & stat.S_IEXEC)
	def test_overwrite_files(
		self, answers=(Yes, Yes), expect_overrides=(True, True),
		files=('a.txt', 'b.txt'), copy=None
	):
		if copy is None:
			copy = files
		src_files = [join(self.src, *relpath.split('/')) for relpath in files]
		for file_path in src_files:
			makedirs(dirname(file_path), exist_ok=True)
			with open(file_path, 'w') as f:
				f.write(basename(file_path))
		copy_paths = [join(self.src, file_name) for file_name in copy]
		self._perform_copy(*copy_paths)
		dest_files = [join(self.dst, file_name) for file_name in files]
		for dest_path in dest_files:
			with open(dest_path, 'w') as f:
				f.write('x')
		for i, answer in enumerate(answers):
			file_name = basename(files[i])
			self._expect_prompt(
				('%s exists. Do you want to override it?' % file_name,
				 Yes | No | YesToAll | NoToAll | Abort, Yes),
				answer=answer
			)
		self._perform_copy(*copy_paths)
		for i, expect_override in enumerate(expect_overrides):
			dest_file = dest_files[i]
			if expect_override:
				self._assert_contents_are_equal(src_files[i], dest_file)
			else:
				with open(dest_file, 'r') as f:
					self.assertEquals(
						'x', f.read(),
						'File %s was overwritten, contrary to expectations.' %
						basename(dest_file)
					)
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
			files=('dir/a.txt', 'b.txt'), copy=('dir', 'b.txt')
		)
	def test_copy_to_self(self):
		a, b = join(self.dst, 'a'), join(self.dst, 'b')
		self._touch(a)
		self._touch(b)
		# Expect prompt only once:
		self._expect_prompt(('You cannot copy a file to itself.', Ok, Ok), Ok)
		self._perform_copy(a, b, __file__)
		# Should still have copied __file__:
		self.assertEquals(
			{'a', 'b', basename(__file__)}, set(listdir(self.dst))
		)
	def setUp(self):
		self.gui_thread = StubGuiThread(self)
		self._src = TemporaryDirectory()
		self._dst = TemporaryDirectory()
		# Create a dummy file to test that not _all_ files are copied from src:
		self._touch(join(self.src, 'dummy'))
	def _perform_copy(self, *files):
		CopyFiles(self.gui_thread, files, self.dst, self.src)()
		self.gui_thread.verify_expected_prompts_were_shown()
	@property
	def src(self):
		return self._src.name
	@property
	def dst(self):
		return self._dst.name
	def tearDown(self):
		self._src.cleanup()
		self._dst.cleanup()
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