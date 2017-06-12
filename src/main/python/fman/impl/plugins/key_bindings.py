def sanitize_key_bindings(bindings, available_commands):
	if not isinstance(bindings, list):
		return [], [('Error: Key bindings should be a list [...], not %s.' %
					 _describe_type(bindings))]
	result, errors = [], []
	for binding in bindings:
		this_binding_errors = []
		try:
			command = binding['command']
		except KeyError:
			this_binding_errors.append(
				'Error: Each key binding must specify a "command".'
			)
		else:
			if not isinstance(command, str):
				this_binding_errors.append(
					'Error: A key binding\'s "command" must be a string "...", '
					'not %s.' % _describe_type(command)
				)
			else:
				if command not in available_commands:
					this_binding_errors.append(
						'Error in key bindings: Command %r does not exist.'
						% command
					)
		try:
			keys = binding['keys']
		except KeyError:
			this_binding_errors.append(
				'Error: Each key binding must specify "keys": [...].'
			)
		else:
			if not isinstance(keys, list):
				this_binding_errors.append(
					'Error: A key binding\'s "keys" must be a list ["..."], '
					'not %s.' % _describe_type(keys)
				)
		if this_binding_errors:
			errors.extend(this_binding_errors)
		else:
			result.append(binding)
	return result, errors

def _describe_type(value):
	if isinstance(value, dict):
		return '{...}'
	if isinstance(value, str):
		return '"..."'
	return type(value).__name__