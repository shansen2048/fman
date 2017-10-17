from fman.util import ConstructorMixin, EqMixin, ReprMixin

class ComputeDiff:
	"""
	N.B.: This implementation requires that there be no duplicate rows!
	"""
	def __init__(self, old_rows, new_rows):
		self._old_rows = list(old_rows)
		self._new_rows = new_rows
		self._result = []
	def __call__(self):
		for i in range(len(self._old_rows)-1, -1, -1):
			if self._old_rows[i] not in self._new_rows:
				self._remove_row(i)
		for i, new_row in enumerate(self._new_rows):
			if new_row not in self._old_rows:
				self._insert_row(i, new_row)
		for i, new_row in enumerate(self._new_rows):
			if new_row != self._old_rows[i]:
				self._move_row(self._old_rows.index(new_row, i), i)
		assert self._old_rows == self._new_rows
		return self._join_adjacent()
	def _remove_row(self, i):
		self._result.append(DiffEntry(i, i + 1, 0, []))
		self._old_rows.pop(i)
	def _insert_row(self, i, row):
		self._result.append(DiffEntry(0, 0, i, [row]))
		self._old_rows.insert(i, row)
	def _move_row(self, src, dest):
		row = self._old_rows.pop(src)
		self._old_rows.insert(dest, row)
		self._result.append(DiffEntry(src, src + 1, dest, [row]))
	def _join_adjacent(self):
		if not self._result:
			return []
		result = [self._result[0]]
		for entry in self._result[1:]:
			if not result[-1].extend_by(entry):
				result.append(entry)
		return result

class DiffEntry(ConstructorMixin, EqMixin, ReprMixin):

	_FIELDS = ('cut_start', 'cut_end', 'insert_start', 'rows')

	def extend_by(self, other):
		if not self.rows and other.cut_start == self.cut_end:
			self.cut_end = other.cut_end
			self.rows = other.rows
			return True
		if not other.rows and other.cut_end == self.cut_start:
			self.cut_start = other.cut_start
			return True
		if not other.does_cut and other.insert_start == self.insert_end:
			self.rows += other.rows
			return True
		return False
	@property
	def type(self):
		if not self.does_cut:
			assert self.rows
			return 'insert'
		if self.rows:
			if self.cut_end - self.cut_start == len(self.rows):
				if self.cut_start == self.insert_start:
					return 'change'
				else:
					return 'move'
			return 'other'
		else:
			return 'remove'
	@property
	def does_cut(self):
		return self.cut_end > self.cut_start
	@property
	def insert_end(self):
		return self.insert_start + len(self.rows)