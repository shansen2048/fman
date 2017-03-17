from collections import namedtuple

import tinycss

Rule = namedtuple('Rule', ('selectors', 'declarations'))
Declaration = namedtuple('Declaration', ('property', 'value'))

def load_css_rules(*paths):
	result = []
	parser = tinycss.make_parser()
	for path in paths:
		try:
			with open(path, 'rb') as f:
				f_contents = f.read()
		except FileNotFoundError:
			continue
		stylesheet = parser.parse_stylesheet_bytes(f_contents)
		for rule in stylesheet.rules:
			selectors = rule.selector.as_css().split(', ')
			declarations = [
				Declaration(decl.name, decl.value.as_css())
				for decl in rule.declarations
			]
			result.append(Rule(selectors, declarations))
	return result

def css_rules_to_qss(rules):
	result_lines = []
	repl = lambda selector: _CSS_TO_QSS.get(selector, selector)
	for rule in rules:
		result_lines.append(', '.join(map(repl, rule.selectors)) + ' {')
		for decl in rule.declarations:
			result_lines.append('\t%s: %s;' % decl)
		result_lines.append('}')
	return '\n'.join(result_lines)

_CSS_TO_QSS = {
	'th': 'QTreeView QHeaderView::section',
	'.statusbar': 'QStatusBar, QStatusBar QLabel',
	'.quicksearch-query': 'Quicksearch QLineEdit',
	'.quicksearch-item-title': 'QuicksearchSuggestion #title',
	'.quicksearch-item-hint': 'QuicksearchSuggestion #hint'
}