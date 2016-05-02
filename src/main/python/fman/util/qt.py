def connect_once(signal, slot):
	def _connect_once(*args, **kwargs):
		slot(*args, **kwargs)
		signal.disconnect(_connect_once)
	signal.connect(_connect_once)