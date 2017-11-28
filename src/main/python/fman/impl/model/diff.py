from fman.impl.util import ConstructorMixin, EqMixin, ReprMixin

class ComputeDiff:
	"""
	N.B.: This implementation requires that there be no duplicate rows!
	"""
	def __init__(self, old_rows, new_rows, key_fn=lambda x: x):
		self._old_rows = list(old_rows)
		self._new_rows = new_rows
		self._key_fn = key_fn
		self._old_keys = list(map(key_fn, old_rows))
		self._new_keys = list(map(key_fn, new_rows))
		self._result = []
	def __call__(self):
		for i in range(len(self._old_keys) - 1, -1, -1):
			if self._old_keys[i] not in self._new_keys:
				self._remove_row(i)
		for i, new_key in enumerate(self._new_keys):
			if new_key not in self._old_keys:
				self._insert_row(i, self._new_rows[i])
		for i, new_key in enumerate(self._new_keys):
			if new_key != self._old_keys[i]:
				old_row_index = self._old_keys.index(new_key, i)
				if old_row_index != i:
					self._move_row(old_row_index, i)
				old_row = self._old_rows[i]
				new_row = self._new_rows[i]
				if old_row != new_row:
					self._update_row(i, new_row)
		assert self._old_keys == self._new_keys
		return self._join_adjacent()
	def _remove_row(self, i):
		self._result.append(DiffEntry(i, i + 1, -1, []))
		self._old_rows.pop(i)
		self._old_keys.pop(i)
	def _insert_row(self, i, row):
		self._result.append(DiffEntry(-1, -1, i, [row]))
		self._old_rows.insert(i, row)
		self._old_keys.insert(i, self._key_fn(row))
	def _move_row(self, src, dest):
		self._result.append(DiffEntry(src, src + 1, dest, []))
		self._old_rows.insert(dest, self._old_rows.pop(src))
		self._old_keys.insert(dest, self._old_keys.pop(src))
	def _update_row(self, i, row):
		self._result.append(DiffEntry(i, i + 1, i, [row]))
		self._old_rows[i] = row
		assert self._key_fn(row) == self._old_keys[i]
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
		if not self.rows:
			if other.cut_start == self.cut_end:
				self.cut_end = other.cut_end
				self.rows = other.rows
				return True
			elif len(other.rows) == self.cut_end - self.cut_start and \
					other.insert_start == self.cut_start:
				# Cut followed by insert
				self.insert_start = other.insert_start
				self.rows = other.rows
				return True
		if not other.rows and other.cut_end == self.cut_start:
			self.cut_start = other.cut_start
			return True
		if not self._does_cut and not other._does_cut and \
				other.insert_start == self._insert_end:
			self.rows += other.rows
			return True
		return False
	def apply(self, insert, move, update, remove):
		if self._does_cut:
			if self.rows:
				assert len(self.rows) == self.cut_end - self.cut_start
				assert self.cut_start == self.insert_start
				update(self.rows, self.cut_start)
			else:
				if self.insert_start != -1:
					move(self.cut_start, self.cut_end, self.insert_start)
				else:
					remove(self.cut_start, self.cut_end)
		else:
			assert self.rows
			assert self.insert_start != -1
			insert(self.rows, self.insert_start)
	@property
	def _does_cut(self):
		return self.cut_end > self.cut_start
	@property
	def _insert_end(self):
		return self.insert_start + len(self.rows)