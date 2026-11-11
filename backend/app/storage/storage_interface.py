import abc
import hashlib
import os
from typing import Dict, Any, Optional

PROHIBITED_EXTENSIONS = {
    ".exe", ".bat", ".cmd", ".sh", ".bash", ".ps1", ".vbs", 
    ".msi", ".dll", ".com", ".scr", ".pif", ".application", 
    ".gadget", ".hta", ".cpl", ".msc", ".jar", ".bin", ".elf", ".sys"
}

PROHIBITED_MIME_TYPES = {
    "application/x-msdownload",
    "application/x-msdos-program",
    "application/x-executable",
    "application/x-sh",
    "application/x-shellscript",
    "application/x-csh",
    "application/x-batch",
}

def is_prohibited_extension(filename: str) -> bool:
    """Returns True if the file extension is dangerous / executable."""
    _, ext = os.path.splitext(filename.lower())
    return ext in PROHIBITED_EXTENSIONS

def is_prohibited_mime_type(mime_type: str) -> bool:
    """Returns True if the MIME type is an executable / dangerous type."""
    return mime_type.lower().strip() in PROHIBITED_MIME_TYPES

class StorageBackend(abc.ABC):
    """
    Abstract storage backend interface.
    Allows seamless transition between MinIO (local Docker) and AWS S3 / Cloud S3 in production.
    """

    @abc.abstractmethod
    def generate_presigned_upload_url(
        self, 
        storage_key: str, 
        content_type: str, 
        max_size_bytes: int,
        expires_in: int = 3600
    ) -> Dict[str, Any]:
        """Generate a secure pre-signed upload URL / form specification."""
        pass

    @abc.abstractmethod
    def generate_presigned_download_url(
        self, 
        storage_key: str, 
        filename: str, 
        expires_in: int = 3600
    ) -> str:
        """Generate a short-lived secure download URL."""
        pass

    @abc.abstractmethod
    def put_object(self, storage_key: str, data: bytes, content_type: str) -> bool:
        """Store an object directly."""
        pass

    @abc.abstractmethod
    def get_object(self, storage_key: str) -> bytes:
        """Retrieve object binary payload."""
        pass

    @abc.abstractmethod
    def delete_object(self, storage_key: str) -> bool:
        """Delete an object permanently."""
        pass

    @abc.abstractmethod
    def object_exists(self, storage_key: str) -> bool:
        """Check if an object exists in the storage bucket."""
        pass

    @abc.abstractmethod
    def list_objects(self, prefix: str = "") -> list:
        """List objects matching prefix in the bucket."""
        pass

    @staticmethod
    def compute_sha256(data: bytes) -> str:
        """Compute the SHA-256 hexadecimal hash of bytes payload."""
        hasher = hashlib.sha256()
        hasher.update(data)
        return hasher.hexdigest()
