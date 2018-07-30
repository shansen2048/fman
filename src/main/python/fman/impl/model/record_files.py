from bisect import bisect_left
from fman.impl.model.diff import DiffEntry
from fman.impl.model.diff import join as join_diff

class RecordFiles:
	"""
	Performance optimization: Implements Model#_record_files(...) in a way that
	is faster than the following naive approach:

		for url in _disappeared:
			del model._files[url]
		for file_ in files:
			model._files[file_.url] = file_
		model.set_rows(model._sorted(model._filter(model.get_rows())))

	This implementation should return the same results as the above pseudo-code.
	It saves ~1s when displaying a directory with 5k files and scrolling
	page-down four times.
	"""
	def __init__(
		self, files, disappeared,
		m_files, m_rows, m_accepts, m_sortval, m_apply_diff
	):
		self._files = files
		self._disappeared = disappeared
		self._m_files = m_files
		self._m_rows = m_rows
		self._m_accepts = m_accepts
		self._m_sortval = m_sortval
		self._m_apply_diff = m_apply_diff
	def __call__(self):
		self._remove_files(self._disappeared)
		to_update = []
		to_remove = []
		to_move = []
		to_insert = []
		for file_ in self._files:
			try:
				old_file = self._m_files[file_.url]
			except KeyError:
				if self._m_accepts(file_):
					to_insert.append(file_)
			else:
				try:
					rownum = self._m_rows.find(file_.url)
				except KeyError:
					if self._m_accepts(file_):
						to_insert.append(file_)
				else:
					if not self._m_accepts(file_):
						to_remove.append(rownum)
						continue
					if file_ != old_file:
						to_update.append((rownum, file_))
					old_sortval = self._m_sortval(old_file)
					new_sortval = self._m_sortval(file_)
					if old_sortval != new_sortval:
						to_move.append((rownum, new_sortval))
			self._m_files[file_.url] = file_
		diff = []
		# First update rows because it doesn't change any row numbers. Sort by
		# rownum to make it possible to join adjacent updates in the diff:
		for rownum, file_ in sorted(to_update):
			diff.append(DiffEntry.update(rownum, [file_]))
		"""
		Next move rows because it doesn't change their total number. We do this
		as follows: Say the existing rows are

			***F*****D***E***H*B*AC****G**    <- "level 0"

		Where * are unchanged rows and A-H are rows to be moved. Split the two:

			*** ***** *** *** * *  **** **    <- "level 1"
			   ^     ^   ^   ^ ^ ^^    ^
			   F     D   E   H B AC    G      <- "level 2"

		Then, we sort level 2. This gives new insertion points:

			* *** ** *  ***** **** ******
			 ^   ^  ^ ^^     ^    ^      ^
			 A   B  C DE     F    G      H

		That is:

			*A****B***C**DE*****F*G******H    <- "goal"

		We then compute and apply the moves required for rearranging level 0
		into the goal.
		"""
		lvl2_rows = (rownum for rownum, _ in to_move)
		sort_values = Lvl1SortValues(self._m_rows, self._m_sortval, lvl2_rows)
		goal = []
		to_move.sort(key=lambda tpl: tpl[1])

		for num_inserted, (lvl0_rownum, sortval) in enumerate(to_move):
			lvl1 = sort_values.get_lvl1_rownum_for(sortval)
			src = lvl1 + num_inserted
			goal.append((src, lvl0_rownum))
		lvl0 = [(rownum, rownum) for rownum, _ in to_move]

		moved = []
		for src, dst in get_moves_for_transforming(lvl0, goal):
			diff.append(DiffEntry.move(src, dst))
			moved.append((src, dst))

		def get_rownum_after_moves(orig_rownum):
			result = orig_rownum
			for src, dst in moved:
				if src <= result:
					result -= 1
				if dst <= result:
					result += 1
			return result

		# Then remove rows because effect on rownums is simple. Sort by rownum
		# then reverse so later removals are not affected by earlier ones:
		rs = sorted(map(get_rownum_after_moves, to_remove), reverse=True)
		for rownum in rs:
			diff.append(DiffEntry.remove(rownum))
		# Flush:
		self._m_apply_diff(join_diff(diff))
		diff = []
		# Finally, insert rows. In reverse order so later inserts are not
		# affected by earlier ones:
		insert_sortvals = ((self._m_sortval(f), f) for f in to_insert)
		for sortval, f in sorted(insert_sortvals, reverse=True):
			rownum = self._get_rownum_for_sortval(sortval)
			diff.append(DiffEntry.insert(rownum, [f]))
		self._m_apply_diff(join_diff(diff))
	def _remove_files(self, files):
		rownums = []
		for url in files:
			try:
				del self._m_files[url]
			except KeyError:
				pass
			else:
				try:
					rownums.append(self._m_rows.find(url))
				except KeyError:
					pass
		diff = [
			# Sort rownums reverse so earlier removals don't affect later ones:
			DiffEntry.remove(rownum) for rownum in sorted(rownums, reverse=True)
		]
		self._m_apply_diff(join_diff(diff))
	def _get_rownum_for_sortval(self, sort_value):
		class SortValues:
			def __len__(_):
				return len(self._m_rows)
			def __getitem__(_, item):
				return self._m_sortval(self._m_rows[item])
		return bisect_left(SortValues(), sort_value)

class Lvl1SortValues:
	def __init__(self, m_rows, m_sortval, lvl2_rownums):
		self._m_rows = m_rows
		self._m_sortval = m_sortval
		self._lvl2_rownums = set(lvl2_rownums)
	def get_lvl1_rownum_for(self, sortval):
		return bisect_left(self, sortval)
	def __len__(self):
		return len(self._m_rows) - len(self._lvl2_rownums)
	def __getitem__(self, item):
		i = self._get_original_index(item)
		return self._m_sortval(self._m_rows[i])
	def _get_original_index(self, i):
		result = -1
		for _ in range(i + 1):
			result += 1
			while result in self._lvl2_rownums:
				result += 1
		return result

def get_moves_for_transforming(curr, goal):
	"""
	Get the index moves [(src, dst), ...] to rearrange a sparse list. Eg.:

	    ***F*****D***E***H*B*AC****G**

	                 to

	    *A****B***C**DE*****F*G******H

	The two parameters are given as lists (index, value). In the above example:

	    curr = [(3, 'F'), (9, 'D'), ...]
	    goal = [(1, 'A'), (6, 'B'), ...]

	The result is the sequence of required moves. In the example, it could be:

	    [(17, 29), (27, 23), ...]

	Visually:

	    ***F*****D***E***H*B*AC****G**
	                     |___________
	                                 |    (17, 29)
	    ***F*****D***E****B*AC****G**H
	                           ___|
	                          |           (27, 23)
	    ***F*****D***E****B*ACG******H

	                 ...

	    *A****B***C**DE*****F*G******H
	"""
	return GetMovesForTransforming(curr, goal)()

class GetMovesForTransforming:
	def __init__(self, curr, goal):
		self._curr = sorted(curr)
		self._goal = sorted(goal)
		self._curr_indices = [index for index, _ in self._curr]
		self._curr_map = {key: index for index, key in self._curr}
		self._goal_map = {key: index for index, key in self._goal}
		self._result = []
	def __call__(self):
		c_i = g_i = len(self._curr) - 1
		while c_i >= 0 or g_i >= 0:
			if g_i >= 0:
				g_index, g_key = self._goal[g_i]
				if c_i < 0 or g_index >= self._curr[c_i][0]:
					src = self._curr_map[g_key]
					self._move(src, g_index)
					g_i -= 1
					continue
			c_index, c_key = self._curr[c_i]
			dst = self._goal_map[c_key]
			self._move(c_index, dst)
			if dst >= c_index:
				c_i -= 1
		return self._result
	def _move(self, src, dst):
		if src == dst:
			return
		self._result.append((src, dst))
		curr_index, key = self._pop(src)
		self._insert(dst, key)
	def _pop(self, src):
		s = bisect_left(self._curr_indices, src)
		result = self._curr.pop(s)
		self._curr_indices.pop(s)
		self._curr_map.pop(result[1])
		for i, (index, key) in enumerate(self._curr[s:], s):
			self._curr[i] = (index - 1, key)
			self._curr_indices[i] = index - 1
			self._curr_map[key] = index - 1
		return result
	def _insert(self, dst, key):
		insert_point = bisect_left(self._curr_indices, dst)
		self._curr.insert(insert_point, (dst, key))
		self._curr_indices.insert(insert_point, dst)
		self._curr_map[key] = dst
		i_start = insert_point + 1
		for i, (index, k) in enumerate(self._curr[i_start:], i_start):
			self._curr[i] = (index + 1, k)
			self._curr_indices[i] = index + 1
			self._curr_map[k] = index + 1