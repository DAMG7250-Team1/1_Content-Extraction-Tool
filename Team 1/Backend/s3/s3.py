# storage_handler.py
import boto3
from botocore.exceptions import ClientError
import logging
import json
import os
from datetime import datetime
from typing import Optional, BinaryIO, Union
from dotenv import load_dotenv
import io

# Load environment variables
load_dotenv()

# Get AWS credentials from environment
AWS_ACCESS_KEY_ID = os.getenv('AWS_ACCESS_KEY_ID')
AWS_SECRET_ACCESS_KEY = os.getenv('AWS_SECRET_ACCESS_KEY')
AWS_REGION = os.getenv('AWS_REGION')

logger = logging.getLogger(__name__)

class StorageHandler:
    def __init__(self, bucket_name: str, aws_access_key_id: str = None, 
                 aws_secret_access_key: str = None, region_name: str = None):
        self.s3_client = boto3.client('s3',
                                    aws_access_key_id=aws_access_key_id or AWS_ACCESS_KEY_ID,
                                    aws_secret_access_key=aws_secret_access_key or AWS_SECRET_ACCESS_KEY,
                                    region_name=region_name or AWS_REGION)
        self.bucket_name = bucket_name

    def upload(self, file_data: Union[BinaryIO, dict], file_path: str, content_type: str) -> Optional[str]:
        """
        Upload a file to S3 storage.
        
        Args:
            file_data: Either a file-like object or a dictionary (for JSON data)
            file_path: The path/key where the file will be stored in S3
            content_type: The MIME type of the content being uploaded
        """
        try:
            # Handle dictionary input (convert to JSON)
            if isinstance(file_data, dict):
                file_data = json.dumps(file_data).encode('utf-8')
                file_data = io.BytesIO(file_data)
                content_type = 'application/json'
            
            # Reset file pointer if it's a file-like object
            if hasattr(file_data, 'seek'):
                file_data.seek(0)
            
            self.s3_client.upload_fileobj(
                file_data,
                self.bucket_name,
                file_path,
                ExtraArgs={'ContentType': content_type}
            )
            return file_path
        
        except Exception as e:
            logger.error(f"Error uploading file to S3: {str(e)}")
            raise

    def download(self, file_path: str) -> Optional[bytes]:
        """Download a file from S3 storage."""
        try:
            response = self.s3_client.get_object(Bucket=self.bucket_name, Key=file_path)
            return response['Body'].read()
        except Exception as e:
            logger.error(f"Error downloading file from S3: {str(e)}")
            raise

    def delete(self, file_path: str) -> bool:
        """Delete a file from S3 storage."""
        try:
            self.s3_client.delete_object(Bucket=self.bucket_name, Key=file_path)
            return True
        except Exception as e:
            logger.error(f"Error deleting file from S3: {str(e)}")
            return False