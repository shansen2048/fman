from fman.url import dirname

def get_existing_pardir(url, is_dir):
	prev_url = None
	while url != prev_url:
		if is_dir(url):
			return url
		prev_url = url
		url = dirname(url)