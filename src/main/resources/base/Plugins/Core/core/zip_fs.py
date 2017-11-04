from fman import DirectoryPaneListener
from fman.url import splitscheme

class ZipOpenListener(DirectoryPaneListener):
	def on_command(self, command, args):
		if command == 'default_open':
			try:
				scheme, path = splitscheme(args['url'])
			except (KeyError, ValueError):
				return None
			if scheme == 'file://' and path.endswith('.zip'):
				new_args = dict(args)
				new_args['url'] = 'zip://' + path
				return command, new_args