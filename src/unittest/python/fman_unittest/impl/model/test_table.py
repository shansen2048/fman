from fman.impl.model.table import _get_move_destination
from unittest import TestCase

class GetMoveDestinationTest(TestCase):
	def test_move_one_row_up(self):
		# Example taken from the Qt docs on QAbstractItemModel#beginMoveRows.
		self.assertEqual(0, _get_move_destination(2, 3, 0))
	def test_move_one_row_one_step_down(self):
		# Example taken from the Qt docs on QAbstractItemModel#beginMoveRows.
		self.assertEqual(4, _get_move_destination(2, 3, 3))
	def test_move_multiple_rows_down_overlapping(self):
		self.assertEqual(4, _get_move_destination(1, 3, 2))
	def test_move_multiple_rows_down_adjacent(self):
		self.assertEqual(5, _get_move_destination(1, 3, 3))
	def test_move_multiple_rows_far_down(self):
		self.assertEqual(6, _get_move_destination(1, 3, 4))
	def test_move_multiple_rows_one_up(self):
		self.assertEqual(1, _get_move_destination(2, 101, 1))
	def test_move_multiple_rows_two_up(self):
		self.assertEqual(0, _get_move_destination(2, 101, 0))
	def test_move_multiple_rows_far_up(self):
		self.assertEqual(2, _get_move_destination(5, 7, 2))