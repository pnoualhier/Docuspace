import hashlib
import hmac
import io
import os
import time
from datetime import timedelta
from typing import Any, Dict, Optional
from urllib.parse import quote, urlencode

from minio import Minio
from minio.commonconfig import CopySource
from minio.error import S3Error

from backend.app.core.config import is_test_runtime, settings
from backend.app.storage.storage_interface import StorageBackend


class StorageBackendError(RuntimeError):
    """Raised when the S3 / MinIO backend fails in fail-closed mode."""


class S3Storage(StorageBackend):
    """
    MinIO & AWS S3 compatible storage implementation.
    Features:
      - Real MinIO Python SDK client in production & when TEST_MINIO_ENDPOINT / use_minio=True is set
      - SigV4 / HMAC pre-signed URLs for direct client-to-storage streaming
      - Strict multi-tenant bucket prefixing: tenants/{tenant_id}/{object_id}
      - Fail-closed behavior in production (never falls back silently to in-memory storage)
      - In-process storage fallback strictly restricted to offline unit tests when no MinIO daemon is configured
    """

    def __init__(
        self,
        endpoint: Optional[str] = None,
        access_key: Optional[str] = None,
        secret_key: Optional[str] = None,
        bucket_name: Optional[str] = None,
        secure: Optional[bool] = None,
        use_minio: Optional[bool] = None,
    ):
        self.endpoint = endpoint or settings.MINIO_ENDPOINT
        self.access_key = access_key if access_key is not None else settings.MINIO_ACCESS_KEY
        self.secret_key = secret_key if secret_key is not None else settings.MINIO_SECRET_KEY
        self.bucket_name = bucket_name or settings.MINIO_BUCKET_NAME
        self.secure = settings.MINIO_SECURE if secure is None else secure
        self.protocol = "https" if self.secure else "http"

        test_minio_ep = os.getenv("TEST_MINIO_ENDPOINT", "").strip()
        if use_minio is not None:
            self._use_minio = use_minio
        elif not is_test_runtime():
            self._use_minio = True
        elif test_minio_ep and self.endpoint == test_minio_ep:
            self._use_minio = True
        else:
            self._use_minio = False

        self._client: Optional[Minio] = None
        self._bucket_verified: bool = False

        # Strictly test-only in-process store
        self._local_storage: Dict[str, bytes] = {}
        self._content_types: Dict[str, str] = {}

    def _get_minio_client(self) -> Minio:
        if self._client is None:
            if not self.endpoint or not self.access_key or not self.secret_key:
                raise StorageBackendError("Configuration MinIO S3 incomplète (endpoint ou identifiants manquants).")
            self._client = Minio(
                self.endpoint,
                access_key=self.access_key,
                secret_key=self.secret_key,
                secure=self.secure,
            )
        return self._client

    def ensure_bucket(self) -> None:
        if not self._use_minio or self._bucket_verified:
            return
        try:
            client = self._get_minio_client()
            if not client.bucket_exists(self.bucket_name):
                client.make_bucket(self.bucket_name)
            self._bucket_verified = True
        except Exception as exc:
            raise StorageBackendError(f"Impossible d'initialiser le bucket MinIO '{self.bucket_name}': {exc}") from exc

    def _sign_url(self, storage_key: str, expires_at: int, action: str = "GET") -> str:
        """Computes HMAC-SHA256 signature for presigned URL authorization (test/local harness)."""
        message = f"{action}\n{self.bucket_name}\n{storage_key}\n{expires_at}"
        signature = hmac.new(
            self.secret_key.encode("utf-8"),
            message.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        return signature

    def generate_presigned_upload_url(
        self,
        storage_key: str,
        content_type: str,
        max_size_bytes: int,
        expires_in: int = 3600,
    ) -> Dict[str, Any]:
        """
        Generates S3 Presigned Upload parameters.
        Uses real MinIO SigV4 presigned PUT URL when MinIO SDK is active.
        """
        expires_at = int(time.time()) + expires_in
        if self._use_minio:
            self.ensure_bucket()
            try:
                client = self._get_minio_client()
                signed_url = client.presigned_put_object(
                    self.bucket_name,
                    storage_key,
                    expires=timedelta(seconds=expires_in),
                )
            except Exception as exc:
                raise StorageBackendError(f"Échec génération URL pré-signée MinIO upload: {exc}") from exc
        else:
            sig = self._sign_url(storage_key, expires_at, action="PUT")
            params = {
                "AWSAccessKeyId": self.access_key,
                "Expires": str(expires_at),
                "Signature": sig,
                "maxSizeBytes": str(max_size_bytes),
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
                "x-amz-acl": "private",
            },
        }

    def generate_presigned_download_url(
        self,
        storage_key: str,
        filename: str,
        expires_in: int = 3600,
    ) -> str:
        """
        Generates a secure, time-limited S3 pre-signed download URL
        with Content-Disposition attachment header.
        """
        safe_filename = os.path.basename(filename or "document").replace('"', "_")
        encoded_filename = quote(safe_filename)
        disposition = f'attachment; filename="{encoded_filename}"'

        if self._use_minio:
            self.ensure_bucket()
            try:
                client = self._get_minio_client()
                return client.presigned_get_object(
                    self.bucket_name,
                    storage_key,
                    expires=timedelta(seconds=expires_in),
                    response_headers={"response-content-disposition": disposition},
                )
            except Exception as exc:
                raise StorageBackendError(f"Échec génération URL pré-signée MinIO download: {exc}") from exc

        expires_at = int(time.time()) + expires_in
        sig = self._sign_url(storage_key, expires_at, action="GET")
        params = {
            "AWSAccessKeyId": self.access_key,
            "Expires": str(expires_at),
            "Signature": sig,
            "response-content-disposition": disposition,
        }
        base_url = f"{self.protocol}://{self.endpoint}/{self.bucket_name}/{storage_key}"
        return f"{base_url}?{urlencode(params)}"

    def verify_presigned_token(self, storage_key: str, expires_at: int, signature: str, action: str = "GET") -> bool:
        """Verifies if an HMAC presigned signature is authentic and unexpired."""
        if int(time.time()) > expires_at:
            return False
        expected_sig = self._sign_url(storage_key, expires_at, action)
        return hmac.compare_digest(expected_sig, signature)

    def put_object(self, storage_key: str, data: bytes, content_type: str = "application/octet-stream") -> bool:
        """Stores object bytes directly in MinIO (or test store in offline test runtime)."""
        if self._use_minio:
            self.ensure_bucket()
            try:
                client = self._get_minio_client()
                client.put_object(
                    self.bucket_name,
                    storage_key,
                    io.BytesIO(data),
                    length=len(data),
                    content_type=content_type or "application/octet-stream",
                )
                return True
            except Exception as exc:
                raise StorageBackendError(f"Échec écriture objet MinIO '{storage_key}': {exc}") from exc

        self._local_storage[storage_key] = data
        self._content_types[storage_key] = content_type
        return True

    def get_object(self, storage_key: str) -> bytes:
        """Retrieves object bytes from MinIO (or test store in offline test runtime)."""
        if self._use_minio:
            self.ensure_bucket()
            response = None
            try:
                client = self._get_minio_client()
                response = client.get_object(self.bucket_name, storage_key)
                return response.read()
            except S3Error as exc:
                if exc.code in ("NoSuchKey", "NoSuchObject", "NoSuchBucket"):
                    raise FileNotFoundError(
                        f"Storage object '{storage_key}' not found in bucket '{self.bucket_name}'"
                    ) from exc
                raise StorageBackendError(f"Erreur lecture MinIO '{storage_key}': {exc}") from exc
            except Exception as exc:
                raise StorageBackendError(f"Erreur connexion MinIO '{storage_key}': {exc}") from exc
            finally:
                if response is not None:
                    response.close()
                    response.release_conn()

        if storage_key not in self._local_storage:
            raise FileNotFoundError(f"Storage object '{storage_key}' not found in bucket '{self.bucket_name}'")
        return self._local_storage[storage_key]

    def copy_object(self, source_key: str, dest_key: str) -> bool:
        """Copies an object within the bucket in MinIO (or test store)."""
        if self._use_minio:
            self.ensure_bucket()
            try:
                client = self._get_minio_client()
                client.copy_object(
                    self.bucket_name,
                    dest_key,
                    CopySource(self.bucket_name, source_key),
                )
                return True
            except S3Error as exc:
                if exc.code in ("NoSuchKey", "NoSuchObject", "NoSuchBucket"):
                    raise FileNotFoundError(
                        f"Source storage object '{source_key}' not found in bucket '{self.bucket_name}'"
                    ) from exc
                raise StorageBackendError(f"Erreur copie MinIO '{source_key}' -> '{dest_key}': {exc}") from exc
            except Exception as exc:
                raise StorageBackendError(f"Erreur copie MinIO '{source_key}' -> '{dest_key}': {exc}") from exc

        if source_key not in self._local_storage:
            raise FileNotFoundError(f"Source storage object '{source_key}' not found in bucket '{self.bucket_name}'")
        self._local_storage[dest_key] = self._local_storage[source_key]
        self._content_types[dest_key] = self._content_types.get(source_key, "application/octet-stream")
        return True

    def delete_object(self, storage_key: str) -> bool:
        """Deletes object from MinIO (or test store)."""
        if self._use_minio:
            self.ensure_bucket()
            try:
                client = self._get_minio_client()
                client.remove_object(self.bucket_name, storage_key)
                return True
            except S3Error as exc:
                if exc.code in ("NoSuchKey", "NoSuchObject"):
                    return True
                raise StorageBackendError(f"Erreur suppression MinIO '{storage_key}': {exc}") from exc
            except Exception as exc:
                raise StorageBackendError(f"Erreur suppression MinIO '{storage_key}': {exc}") from exc

        self._local_storage.pop(storage_key, None)
        self._content_types.pop(storage_key, None)
        return True

    def object_exists(self, storage_key: str) -> bool:
        """Returns True if object exists in MinIO (or test store)."""
        if self._use_minio:
            self.ensure_bucket()
            try:
                client = self._get_minio_client()
                client.stat_object(self.bucket_name, storage_key)
                return True
            except S3Error as exc:
                if exc.code in ("NoSuchKey", "NoSuchObject", "NoSuchBucket"):
                    return False
                raise StorageBackendError(f"Erreur stat_object MinIO '{storage_key}': {exc}") from exc
            except Exception as exc:
                raise StorageBackendError(f"Erreur stat_object MinIO '{storage_key}': {exc}") from exc

        return storage_key in self._local_storage

    def list_objects(self, prefix: str = "") -> list:
        """Lists objects matching prefix in the bucket."""
        if self._use_minio:
            self.ensure_bucket()
            try:
                client = self._get_minio_client()
                objs = client.list_objects(self.bucket_name, prefix=prefix, recursive=True)
                return [{"key": o.object_name, "size": o.size or 0} for o in objs]
            except Exception as exc:
                raise StorageBackendError(f"Erreur list_objects MinIO prefix='{prefix}': {exc}") from exc

        results = []
        for key, data in self._local_storage.items():
            if key.startswith(prefix):
                results.append({"key": key, "size": len(data)})
        return results

    def check_health(self) -> Dict[str, Any]:
        """Verifies real MinIO connectivity & bucket readiness."""
        if not self._use_minio:
            return {"status": "test_mode", "bucket": self.bucket_name, "use_minio": False}
        client = self._get_minio_client()
        exists = client.bucket_exists(self.bucket_name)
        return {"status": "ok" if exists else "bucket_missing", "bucket": self.bucket_name, "use_minio": True}


# Global singleton storage client instance
storage_client = S3Storage()
