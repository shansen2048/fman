from fman.impl.plugins.config.css import load_css_rules, Rule, Declaration
from fman_integrationtest import get_resource
from unittest import TestCase

class LoadCSSRulesTest(TestCase):
	def test_load_css_rules(self):
		self.maxDiff = None
		css_file = get_resource('LoadCSSRulesTest/Theme.css')
		self.assertEquals([
			Rule(['*'], [Declaration('font-size', '1pt')]),
			Rule(['.a'], [Declaration('font-size', '2pt')]),
			Rule(['.a', '.b'], [Declaration('font-size', '3pt')]),
		], load_css_rules(css_file))