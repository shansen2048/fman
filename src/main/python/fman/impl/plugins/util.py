def describe_type(value):
	if isinstance(value, dict):
		return '{...}'
	if isinstance(value, str):
		return '"..."'
	if isinstance(value, list):
		return '[...]'
	return type(value).__name__