from fman.impl.model import FileSystemModel
from unittest import TestCase

class GetMoveDestinationTest(TestCase):
	def test_move_one_row_up(self):
		# Example taken from the Qt docs on QAbstractItemModel#beginMoveRows.
		self.assertEqual(0, FileSystemModel._get_move_destination(2, 0, 1))
	def test_move_one_row_one_step_down(self):
		# Example taken from the Qt docs on QAbstractItemModel#beginMoveRows.
		self.assertEqual(4, FileSystemModel._get_move_destination(2, 3, 1))
	def test_move_multiple_rows_down_overlapping(self):
		self.assertEqual(4, FileSystemModel._get_move_destination(1, 2, 2))
	def test_move_multiple_rows_down_adjacent(self):
		self.assertEqual(5, FileSystemModel._get_move_destination(1, 3, 2))
	def test_move_multiple_rows_far_down(self):
		self.assertEqual(6, FileSystemModel._get_move_destination(1, 4, 2))
	def test_move_multiple_rows_one_up(self):
		self.assertEqual(1, FileSystemModel._get_move_destination(2, 1, 99))
	def test_move_multiple_rows_two_up(self):
		self.assertEqual(0, FileSystemModel._get_move_destination(2, 0, 99))
	def test_move_multiple_rows_far_up(self):
		self.assertEqual(2, FileSystemModel._get_move_destination(5, 2, 2))