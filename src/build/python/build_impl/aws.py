from fbs import SETTINGS
from time import time

def upload_to_s3(src_path, dest_path):
	_get_aws_bucket().upload_file(
		src_path, dest_path, ExtraArgs={'ACL': 'public-read'}
	)

def create_cloudfront_invalidation(items):
	import boto3
	cloudfront = boto3.client('cloudfront', **_get_aws_credentials())
	cloudfront.create_invalidation(
		DistributionId=SETTINGS['aws_distribution_id'],
		InvalidationBatch={
			'Paths': {
				'Quantity': len(items),
				'Items': items
			},
			'CallerReference': str(int(time()))
		}
	)

def _get_aws_bucket():
	import boto3
	s3 = boto3.resource('s3', **_get_aws_credentials())
	return s3.Bucket(SETTINGS['aws_bucket'])

def _get_aws_credentials():
	return {
		'aws_access_key_id': SETTINGS['aws_access_key_id'],
		'aws_secret_access_key': SETTINGS['aws_secret_access_key']
	}