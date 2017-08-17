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

	def __init__(self, app, qss_file_paths):
		self._app = app
		self._qss_base = ''
		for qss_file_path in qss_file_paths:
			with open(qss_file_path, 'r') as f:
				self._qss_base += f.read() + '\n'
		self._css_rules = []
		self._extra_qss_from_css = ''
	@property
	def qss(self):
		return self._qss_base + self._extra_qss_from_css
	def load(self, css_file_path):
		with open(css_file_path, 'rb') as f:
			f_contents = f.read()
		new_rules = parse_css(f_contents)
		self._css_rules.extend(new_rules)
		for rule in new_rules:
			qss_selectors = self._get_qss_selectors(rule.selectors)
			if not qss_selectors:
				continue
			self._extra_qss_from_css += ', '.join(qss_selectors) + ' {'
			for decl in rule.declarations:
				self._extra_qss_from_css += '\n\t%s: %s;' % decl
			self._extra_qss_from_css += '\n}\n'
		self._app.setStyleSheet(self._qss_base + self._extra_qss_from_css)
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