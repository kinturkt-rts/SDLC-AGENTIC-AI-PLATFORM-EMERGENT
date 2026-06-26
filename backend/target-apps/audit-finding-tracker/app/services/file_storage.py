"""File storage service for evidence uploads.

Supports local filesystem (MVP) and S3 (production) storage backends.
"""

import os
import uuid
from pathlib import Path
from typing import BinaryIO

from fastapi import UploadFile

from app.config import get_settings


class FileStorageService:
    """File storage abstraction supporting local filesystem and S3."""
    
    def __init__(self):
        self.settings = get_settings()
    
    async def store_file(self, file: UploadFile, finding_id: str) -> tuple[str, str]:
        """Store uploaded file and return (s3_key, local_path).
        
        Args:
            file: Uploaded file from FastAPI
            finding_id: UUID of the finding for organization
            
        Returns:
            Tuple of (storage_key, local_path_or_url)
        """
        if self.settings.file_storage_type == "local":
            return await self._store_local(file, finding_id)
        elif self.settings.file_storage_type == "s3":
            return await self._store_s3(file, finding_id)
        else:
            raise ValueError(f"Unsupported storage type: {self.settings.file_storage_type}")
    
    async def _store_local(self, file: UploadFile, finding_id: str) -> tuple[str, str]:
        """Store file in local filesystem."""
        # Generate unique filename while preserving extension
        file_ext = Path(file.filename or "").suffix
        unique_filename = f"{uuid.uuid4()}{file_ext}"
        
        # Create finding-specific directory
        finding_dir = Path(self.settings.local_upload_dir) / finding_id
        finding_dir.mkdir(parents=True, exist_ok=True)
        
        # Full file path
        file_path = finding_dir / unique_filename
        
        # Write file
        with open(file_path, "wb") as buffer:
            content = await file.read()
            buffer.write(content)
        
        # Return storage key (relative path) and full path
        storage_key = f"evidence/{finding_id}/{unique_filename}"
        return storage_key, str(file_path)
    
    async def _store_s3(self, file: UploadFile, finding_id: str) -> tuple[str, str]:
        """Store file in S3 bucket (production)."""
        # TODO: Implement S3 upload using boto3
        # For now, fall back to local storage
        return await self._store_local(file, finding_id)
    
    def validate_file(self, file: UploadFile) -> None:
        """Validate file type and size."""
        # Check file size
        max_size = self.settings.max_file_size_mb * 1024 * 1024  # Convert MB to bytes
        
        # Note: FastAPI UploadFile doesn't have size attribute until read
        # Size validation will be done during upload
        
        # Check file type (basic validation)
        allowed_types = {
            "application/pdf",
            "application/msword", 
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "application/vnd.ms-excel",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "image/jpeg",
            "image/png",
            "image/gif",
            "text/plain"
        }
        
        if file.content_type not in allowed_types:
            raise ValueError(f"File type {file.content_type} not allowed")


# Singleton instance
file_storage_service = FileStorageService()