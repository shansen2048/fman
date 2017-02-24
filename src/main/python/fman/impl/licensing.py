from base64 import b64decode
from rsa import PublicKey, VerificationError
from rsa.common import byte_size as get_byte_size

import json
import rsa

class LicenseManager:
	def __init__(self, fman_version, email, key):
		self.fman_version = fman_version
		self.email = email
		try:
			self.key_data = unpack_key(key)
		except ValueError:
			self.key_data = {}
	def is_licensed(self):
		try:
			key_email = self.key_data['email']
		except KeyError:
			return False
		if key_email != self.email:
			return False
		max_version = self.key_data.get('max_version', self.fman_version)
		if parse_version(self.fman_version) > parse_version(max_version):
			return False
		return True
	def get_licensee(self):
		return self.email

def unpack_key(key):
	return json.loads(decrypt(key))

def parse_version(version_str):
	if version_str.endswith('-SNAPSHOT'):
		version_str = version_str[:-len('-SNAPSHOT')]
	return tuple(map(int, version_str.split('.')))

def decrypt(data_b64str):
	data = b64decode(data_b64str.encode('ascii'))
	signature_length = get_byte_size(_SIGN_PUB_KEY.n)
	signature, bytes_negated = data[:signature_length], data[signature_length:]
	try:
		rsa.verify(bytes_negated, signature, _SIGN_PUB_KEY)
	except VerificationError:
		raise ValueError('Signature verification failed')
	return _negate(bytes_negated).decode('utf-8')

def _negate(bytes_):
	return bytes(~b % 256 for b in bytes_)

_SIGN_PUB_KEY = PublicKey(146142096601994918206700648259140200952100463274320504063611160294570078501586995967016070398912575192277695142590132973263670517442427130500485732664894774182275447661818963467005949739008288209651168713547437071057019064692363086596546730713984877667901498460512867391678806498712503463981815559532208736523, 65537)