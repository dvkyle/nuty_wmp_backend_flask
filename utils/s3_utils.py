import os
import logging
import boto3
from botocore.exceptions import ClientError

log = logging.getLogger(__name__)

aws_region = os.environ.get("AWS_REGION")
s3_client = boto3.client('s3', region_name=aws_region)

def create_bucket(bucket_name, region=aws_region):
    try:
        location = {'LocationConstraint': aws_region}
        s3_client.create_bucket(Bucket=bucket_name,
                                CreateBucketConfiguration=location)
    except ClientError as e:
        log.error(e)
        return False
    return True

def upload_file(bucket_name, file_name):
    if not bucket_name or not file_name:
        log.info("Cannot upload file {} to bucket {}. A parameter is empty.".format(file_name, bucket_name))
        return

    try:
        s3_client.upload_file(file_name, bucket_name, file_name)
    except ClientError as e:
        log.error(e)
        return False
    return True

def upload_file_data(bucket_name, file_key, file_data, content_type=''):
    if not bucket_name or not file_key or not file_data:
        log.info("Cannot upload to bucket {}, file {}. A parameter is empty.".format(bucket_name, file_key))
        return

    try:
        s3_client.put_object(Bucket=bucket_name, Key=file_key, Body=file_data, ContentType=content_type)
    except ClientError as e:
        log.error(e)
        return False
    return True

def download_file(bucket_name, file_name):
    if not bucket_name or not file_name:
        log.info("Cannot download file {} to bucket {}. A parameter is empty.".format(file_name, bucket_name))
        return

    try:
        s3_client.download_file(bucket_name, file_name, file_name)
    except ClientError as e:
        log.error(e)
        return False
    return True

def download_file_data(bucket_name, file_key):
    try:
        response = s3_client.get_object(Bucket=bucket_name, Key=file_key)
        file_data = response["Body"].read()
        content_type = response["ContentType"]
        return file_data, content_type
    except ClientError as e:
        log.error(e)
        return False
    return True

def delete_file(bucket_name, file_key):
    if not bucket_name or not file_key:
        log.info("Cannot delete file {} from bucket {}. Parameter is missing.".format(file_key, bucket_name))
    
    try:
        s3_client.delete_object(Bucket=bucket_name, Key=file_key)
    except ClientError as e:
        log.error(e)
        return False
    return True
