from fman.util.css import parse_css, CSSEngine
from PyQt5.QtGui import QColor

class CSSQtBridge:

	_CSS_TO_QSS = {
		'th': 'QTreeView QHeaderView::section',
		'.statusbar': 'QStatusBar, QStatusBar QLabel',
		'.quicksearch-query': 'Quicksearch QLineEdit',
		'.quicksearch-item': 'Quicksearch QListView::item'
	}

	def __init__(self, css_file_paths):
		self._css_rules = self._load_css_rules(css_file_paths)
	def _load_css_rules(self, css_file_paths):
		result = []
		for path in css_file_paths:
			try:
				with open(path, 'rb') as f:
					f_contents = f.read()
			except FileNotFoundError:
				continue
			result.extend(parse_css(f_contents))
		return result
	def get_qss(self):
		result_lines = []
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
	def parse_css(self):
		return {
			'quicksearch': {
				'item': self._parse_quicksearch_item_css()
			}
		}
	def _parse_quicksearch_item_css(self):
		engine = CSSEngine(self._css_rules)
		item = engine.query('.quicksearch-item')
		title = engine.query('.quicksearch-item-title')
		title_highlight = engine.query('.quicksearch-item-title-highlight')
		hint = engine.query('.quicksearch-item-hint')
		description = engine.query('.quicksearch-item-description')
		return {
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