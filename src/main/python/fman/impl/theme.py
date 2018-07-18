from collections import OrderedDict
from fman.impl.util.css import parse_css, CSSEngine
from PyQt5.QtGui import QColor
from tinycss.parsing import ParseError

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
		self._css_rules = OrderedDict()
		self._extra_qss_from_css = OrderedDict()
		self._quicksearch_item_css = ''
		self._css_engine = None
		self._updates_enabled = False
	def load(self, css_file_path):
		with open(css_file_path, 'rb') as f:
			f_contents = f.read()
		try:
			new_rules = parse_css(f_contents)
		except ParseError as e:
			raise ThemeError(
				'CSS Parse error in file %s at line %d, column %d: %s'
				% (css_file_path, e.line, e.column, e.reason)
			)
		self._css_rules[css_file_path] = new_rules
		self._extra_qss_from_css[css_file_path] = \
			'\n'.join(map(self._css_rule_to_qss, new_rules))
		try:
			self._quicksearch_item_css = self._get_quicksearch_item_css()
		except ValueError as e:
			error_message = 'CSS error in %s: %s' % (css_file_path, e)
			raise ThemeError(error_message) from None
		self._update_app()
	def unload(self, css_file_path):
		del self._css_rules[css_file_path]
		del self._extra_qss_from_css[css_file_path]
		self._quicksearch_item_css = self._get_quicksearch_item_css()
		self._update_app()
	def get_quicksearch_item_css(self):
		return self._quicksearch_item_css
	def enable_updates(self):
		"""
		Performance optimization: Updating our app's style sheet to reflect
		theme changes is a potentially expensive operation. So we don't want to
		do it after each plugin is loaded when fman starts. Instead, we disable
		updates in the beginning and only enable them once all plugins have been
		loaded.
		"""
		self._updates_enabled = True
		self._update_app()
	def _get_quicksearch_item_css(self):
		self._css_engine = \
			CSSEngine([r for rs in self._css_rules.values() for r in rs])
		return {
			'padding-top_px':
				self._parse_px('.quicksearch-item', 'padding-top'),
			'padding-left_px':
				self._parse_px('.quicksearch-item', 'padding-left'),
			'padding-right_px':
				self._parse_px('.quicksearch-item', 'padding-right'),
			'border-top-width_px':
				self._parse_border_width('.quicksearch-item', 'border-top'),
			'border-bottom-width_px':
				self._parse_border_width('.quicksearch-item', 'border-bottom'),
			'title': {
				'font-size_pts':
					self._parse_pts('.quicksearch-item-title', 'font-size'),
				'color': self._parse_color('.quicksearch-item-title', 'color'),
				'highlight': {
					'color': self._parse_color(
						'.quicksearch-item-title-highlight', 'color'
					)
				}
			},
			'hint': {
				'font-size_pts':
					self._parse_pts('.quicksearch-item-hint', 'font-size'),
				'color': self._parse_color('.quicksearch-item-hint', 'color')
			},
			'description': {
				'font-size_pts': self._parse_pts(
					'.quicksearch-item-description', 'font-size'
				),
				'color':
					self._parse_color('.quicksearch-item-description', 'color')
			}
		}
	def _css_rule_to_qss(self, rule):
		qss_selectors = self._get_qss_selectors(rule.selectors)
		if not qss_selectors:
			return ''
		result = ', '.join(qss_selectors) + ' {'
		for decl in rule.declarations:
			result += '\n\t%s: %s;' % decl
		result += '\n}'
		return result
	def _get_qss_selectors(self, css_selectors):
		result = []
		for css_selector in css_selectors:
			try:
				result.append(self._CSS_TO_QSS[css_selector])
			except KeyError:
				continue
		return result
	def _update_app(self):
		if not self._updates_enabled:
			return
		qss = self._qss_base + ''.join(self._extra_qss_from_css.values())
		self._app.set_style_sheet(qss)
	def _parse_border_width(self, selector, declaration):
		value = self._query(selector, declaration)
		width = value.split(' ')[0]
		error_message = \
			'Invalid value for %s %s: %r. Should be of the form ' \
			'"123px solid #ff0000".' % (selector, declaration, value)
		if not width.endswith('px'):
			raise ValueError(error_message)
		try:
			return int(width[:-2])
		except ValueError:
			raise ValueError(error_message) from None
	def _parse_pts(self, selector, declaration):
		value = self._query(selector, declaration)
		error_message = \
			'Invalid pt value for %s %s: %r' % (selector, declaration, value)
		if not value.endswith('pt'):
			raise ValueError(error_message)
		try:
			return int(value[:-2])
		except ValueError:
			raise ValueError(error_message) from None
	def _parse_color(self, selector, declaration):
		value = self._query(selector, declaration)
		return QColor(value)
	def _parse_px(self, selector, declaration):
		value = self._query(selector, declaration)
		error_message = \
			'Invalid px value for %s %s: %r' % (selector, declaration, value)
		if not value.endswith('px'):
			raise ValueError(error_message)
		try:
			return int(value[:-2])
		except ValueError:
			raise ValueError(error_message) from None
	def _query(self, selector, declaration):
		declarations = self._css_engine.query(selector)
		try:
			return declarations[declaration]
		except KeyError:
			raise ValueError(
				'Could not find %s for %s' % (declaration, selector)
			)

class ThemeError(Exception):
	@property
	def description(self):
		return self.args[0]