"""
Old boto3 S3 patterns that need migration.
Uses deprecated patterns and old API styles from boto3 1.26.x
"""
import boto3
from botocore.config import Config

# Old pattern: Using legacy endpoint_url configuration
s3_client = boto3.client(
    's3',
    region_name='us-east-1',
    # Deprecated: Using legacy SSL verification disable pattern
    verify=False,
    # Old config pattern
    config=Config(
        signature_version='s3',  # Deprecated: should use 's3v4'
        s3={'addressing_style': 'path'}  # Deprecated: path-style addressing
    )
)

# Old pattern: Using deprecated get_bucket_acl without proper error handling
def get_bucket_permissions(bucket_name):
    """Old pattern for getting bucket ACL."""
    acl = s3_client.get_bucket_acl(Bucket=bucket_name)
    return acl

# Old pattern: Using deprecated put_object with legacy ContentType handling
def upload_file_old_style(bucket, key, data):
    """Old upload pattern without proper content type detection."""
    s3_client.put_object(
        Bucket=bucket,
        Key=key,
        Body=data,
        # Deprecated: Manual ACL setting (should use bucket policies)
        ACL='public-read',
        # Old pattern: Not using ServerSideEncryption
    )

# Old pattern: Using deprecated copy_object syntax
def copy_object_legacy(src_bucket, src_key, dst_bucket, dst_key):
    """Legacy copy pattern."""
    copy_source = '%s/%s' % (src_bucket, src_key)  # Old string formatting
    s3_client.copy_object(
        CopySource=copy_source,  # Should use dict format
        Bucket=dst_bucket,
        Key=dst_key
    )

# Old pattern: Paginator without proper async handling
def list_all_objects_sync(bucket):
    """Old synchronous pagination pattern."""
    paginator = s3_client.get_paginator('list_objects')  # Deprecated: use list_objects_v2
    result = []
    for page in paginator.paginate(Bucket=bucket):
        if 'Contents' in page:
            for obj in page['Contents']:
                result.append(obj['Key'])
    return result

# Old pattern: Using deprecated generate_presigned_url parameters
def get_presigned_url_legacy(bucket, key):
    """Legacy presigned URL generation."""
    url = s3_client.generate_presigned_url(
        'get_object',
        Params={
            'Bucket': bucket,
            'Key': key
        },
        ExpiresIn=3600,
        HttpMethod='GET'  # Deprecated parameter
    )
    return url

# Old pattern: Using legacy resource API (being phased out)
s3_resource = boto3.resource('s3')

def upload_with_resource(bucket_name, key, file_path):
    """Old resource-based upload."""
    bucket = s3_resource.Bucket(bucket_name)
    bucket.upload_file(file_path, key)
