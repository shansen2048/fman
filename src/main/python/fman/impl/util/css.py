from collections import namedtuple

import tinycss

Rule = namedtuple('Rule', ('selectors', 'declarations'))
Declaration = namedtuple('Declaration', ('property', 'value'))

def parse_css(bytes_):
	result = []
	parser = tinycss.make_parser()
	stylesheet = parser.parse_stylesheet_bytes(bytes_)
	if stylesheet.errors:
		raise stylesheet.errors[0]
	for rule in stylesheet.rules:
		selectors = rule.selector.as_css().split(', ')
		declarations = [
			Declaration(decl.name, decl.value.as_css())
			for decl in rule.declarations
		]
		result.append(Rule(selectors, declarations))
	return result

class CSSEngine:
	def __init__(self, parsed_css):
		self._rules = parsed_css
	def query(self, selector):
		result = {}
		for rule in self._rules:
			for sel in rule.selectors:
				if sel == '*' or sel == selector:
					for declaration in rule.declarations:
						result[declaration.property] = declaration.value
		return result