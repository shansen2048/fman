def sanitize_key_bindings(bindings, available_commands):
	if not isinstance(bindings, list):
		error = 'Error: Key bindings should be a list ([...]), not %s.' % \
				type(bindings).__name__
		return [], [error]
	result, errors = [], []
	for binding in bindings:
		try:
			command = binding['command']
		except KeyError:
			errors.append('Error: Each key binding must specify a "command".')
		else:
			if not isinstance(command, str):
				errors.append(
					'Error: A key binding\'s "command" must be a '
					'string, not %s.' % type(command).__name__
				)
			else:
				if command not in available_commands:
					errors.append(
						'Error in key bindings: Command %r does not exist.'
						% command
					)
				else:
					result.append(binding)
	return result, errors