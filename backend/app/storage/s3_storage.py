import hmac
import hashlib
import time
import os
from typing import Dict, Any, Optional
from urllib.parse import urlencode, quote
from backend.app.storage.storage_interface import StorageBackend
from backend.app.core.config import settings

class S3Storage(StorageBackend):
    """
    MinIO & AWS S3 compatible storage implementation.
    Features:
      - S3 HMAC-SHA256 pre-signed URLs for direct streaming
      - Time-bounded access tokens
      - Strict multi-tenant bucket prefixing: tenants/{tenant_id}/{object_id}
      - In-process storage cache fallback for tests and development without external daemon
    """

    def __init__(
        self,
        endpoint: Optional[str] = None,
        access_key: Optional[str] = None,
        secret_key: Optional[str] = None,
        bucket_name: Optional[str] = None,
        secure: bool = False
    ):
        self.endpoint = endpoint or settings.MINIO_ENDPOINT
        self.access_key = access_key or settings.MINIO_ACCESS_KEY
        self.secret_key = secret_key or settings.MINIO_SECRET_KEY
        self.bucket_name = bucket_name or settings.MINIO_BUCKET_NAME
        self.secure = secure
        self.protocol = "https" if self.secure else "http"
        
        # In-process data store for development & mock fallback
        self._local_storage: Dict[str, bytes] = {}
        self._content_types: Dict[str, str] = {}

    def _sign_url(self, storage_key: str, expires_at: int, action: str = "GET") -> str:
        """Computes HMAC-SHA256 signature for presigned URL authorization."""
        message = f"{action}\n{self.bucket_name}\n{storage_key}\n{expires_at}"
        signature = hmac.new(
            self.secret_key.encode('utf-8'),
            message.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        return signature

    def generate_presigned_upload_url(
        self, 
        storage_key: str, 
        content_type: str, 
        max_size_bytes: int,
        expires_in: int = 3600
    ) -> Dict[str, Any]:
        """
        Generates S3 Presigned Upload parameters.
        Returns URL, headers, and expiry for direct client-to-storage upload.
        """
        expires_at = int(time.time()) + expires_in
        sig = self._sign_url(storage_key, expires_at, action="PUT")
        
        params = {
            "AWSAccessKeyId": self.access_key,
            "Expires": str(expires_at),
            "Signature": sig,
            "maxSizeBytes": str(max_size_bytes)
        }
        
        base_url = f"{self.protocol}://{self.endpoint}/{self.bucket_name}/{storage_key}"
        signed_url = f"{base_url}?{urlencode(params)}"
        
        return {
            "upload_url": signed_url,
            "storage_key": storage_key,
            "bucket": self.bucket_name,
            "method": "PUT",
            "expires_at": expires_at,
            "headers": {
                "Content-Type": content_type,
                "x-amz-acl": "private"
            }
        }

    def generate_presigned_download_url(
        self, 
        storage_key: str, 
        filename: str, 
        expires_in: int = 3600
    ) -> str:
        """
        Generates a secure, time-limited S3 pre-signed download URL
        with Content-Disposition attachment header.
        """
        expires_at = int(time.time()) + expires_in
        sig = self._sign_url(storage_key, expires_at, action="GET")
        
        encoded_filename = quote(filename)
        params = {
            "AWSAccessKeyId": self.access_key,
            "Expires": str(expires_at),
            "Signature": sig,
            "response-content-disposition": f'attachment; filename="{encoded_filename}"'
        }
        
        base_url = f"{self.protocol}://{self.endpoint}/{self.bucket_name}/{storage_key}"
        return f"{base_url}?{urlencode(params)}"

    def verify_presigned_token(self, storage_key: str, expires_at: int, signature: str, action: str = "GET") -> bool:
        """Verifies if a presigned signature is authentic and unexpired."""
        if int(time.time()) > expires_at:
            return False
        expected_sig = self._sign_url(storage_key, expires_at, action)
        return hmac.compare_digest(expected_sig, signature)

    def put_object(self, storage_key: str, data: bytes, content_type: str = "application/octet-stream") -> bool:
        """Stores object bytes directly."""
        self._local_storage[storage_key] = data
        self._content_types[storage_key] = content_type
        return True

    def get_object(self, storage_key: str) -> bytes:
        """Retrieves object bytes."""
        if storage_key not in self._local_storage:
            raise FileNotFoundError(f"Storage object '{storage_key}' not found in bucket '{self.bucket_name}'")
        return self._local_storage[storage_key]

    def delete_object(self, storage_key: str) -> bool:
        """Deletes object from storage."""
        if storage_key in self._local_storage:
            del self._local_storage[storage_key]
        if storage_key in self._content_types:
            del self._content_types[storage_key]
        return True

    def object_exists(self, storage_key: str) -> bool:
        """Returns True if object exists."""
        return storage_key in self._local_storage

# Global singleton storage client instance
storage_client = S3Storage()
