from fman.util.css import parse_css, CSSEngine
from PyQt5.QtGui import QColor

class Theme:

	_CSS_TO_QSS = {
		'*': '*',
		'th': 'QTableView QHeaderView::section',
		'.statusbar': 'QStatusBar, QStatusBar QLabel',
		'.quicksearch-query': 'Quicksearch QLineEdit',
		'.quicksearch-item': 'Quicksearch QListView::item'
	}

	def __init__(self, qss_file_paths):
		self._css_rules = []
		self._qss = self._load_qss(qss_file_paths)
	@property
	def qss(self):
		return self._qss
	def load(self, css_file_path):
		with open(css_file_path, 'rb') as f:
			f_contents = f.read()
		self._css_rules.extend(parse_css(f_contents))
	def _load_qss(self, qss_files):
		result_lines = []
		for qss_file in qss_files:
			with open(qss_file, 'r') as f:
				result_lines.append(f.read())
		for rule in self._css_rules:
			qss_selectors = self._get_qss_selectors(rule.selectors)
			if not qss_selectors:
				continue
			result_lines.append(', '.join(qss_selectors) + ' {')
			for decl in rule.declarations:
				result_lines.append('\t%s: %s;' % decl)
			result_lines.append('}')
		return '\n'.join(result_lines)
	def _get_qss_selectors(self, css_selectors):
		result = []
		for css_selector in css_selectors:
			try:
				result.append(self._CSS_TO_QSS[css_selector])
			except KeyError:
				continue
		return result
	def get_quicksearch_item_css(self):
		engine = CSSEngine(self._css_rules)
		item = engine.query('.quicksearch-item')
		title = engine.query('.quicksearch-item-title')
		title_highlight = engine.query('.quicksearch-item-title-highlight')
		hint = engine.query('.quicksearch-item-hint')
		description = engine.query('.quicksearch-item-description')
		return {
			'padding-top_px': self._parse_px(item['padding-top']),
			'padding-left_px': self._parse_px(item['padding-left']),
			'padding-right_px': self._parse_px(item['padding-right']),
			'border-top-width_px': self._parse_border_width(item['border-top']),
			'border-bottom-width_px':
				self._parse_border_width(item['border-bottom']),
			'title': {
				'font-size_pts': self._parse_pts(title['font-size']),
				'color': self._parse_color(title['color']),
				'highlight': {
					'color': self._parse_color(title_highlight['color'])
				}
			},
			'hint': {
				'font-size_pts': self._parse_pts(hint['font-size']),
				'color': self._parse_color(hint['color'])
			},
			'description': {
				'font-size_pts': self._parse_pts(description['font-size']),
				'color': self._parse_color(description['color'])
			}
		}
	def _parse_border_width(self, value):
		return self._parse_px(value.split(' ')[0])
	def _parse_pts(self, value):
		if not value.endswith('pt'):
			raise ValueError('Invalid pt value: %r' % value)
		return int(value[:-2])
	def _parse_color(self, value):
		return QColor(value)
	def _parse_px(self, value):
		if not value.endswith('px'):
			raise ValueError('Invalid px value: %r' % value)
		return int(value[:-2])