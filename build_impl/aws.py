from build import AWS_CREDENTIALS, AWS_BUCKET, AWS_DISTRIBUTION_ID
from time import time

import boto3

def upload_to_s3(src_path, dest_path):
	s3 = boto3.resource('s3', **AWS_CREDENTIALS)
	s3.Bucket(AWS_BUCKET).upload_file(
		src_path, dest_path, ExtraArgs={'ACL': 'public-read'}
	)

def create_cloudfront_invalidation(items):
	cloudfront = boto3.client('cloudfront', **AWS_CREDENTIALS)
	cloudfront.create_invalidation(
		DistributionId=AWS_DISTRIBUTION_ID,
		InvalidationBatch={
			'Paths': {
				'Quantity': len(items),
				'Items': items
			},
			'CallerReference': str(int(time()))
		}
	)