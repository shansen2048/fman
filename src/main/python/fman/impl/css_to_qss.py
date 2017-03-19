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
	'.quicksearch-item-title': 'QuicksearchItem #title',
	'.quicksearch-item-hint': 'QuicksearchItem #hint'
}