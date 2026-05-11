# core/attachment_validator.py
import json
from pathlib import Path
from typing import List, Dict, Optional
from core.attachment_config_manager import AttachmentConfigManager
from core.validation_result import ValidationResult
from database.models import AttachmentValidationRule

class AttachmentValidator:
    """Attachment validator - validates file types and sizes"""

    def __init__(self, config_manager: AttachmentConfigManager):
        self.config_mgr = config_manager

    async def validate_attachments(
        self,
        attachments: List[Dict]
    ) -> ValidationResult:
        """
        Validate attachments

        Args:
            attachments: List of attachments, e.g. [{'filename': 'a.pdf', 'content': b'...', 'size': 1024}, ...]

        Returns:
            ValidationResult
        """
        # Get current rules
        rules = await self.config_mgr.get_current_rules()

        if not rules:
            # No rules configured, reject all
            return ValidationResult(
                is_valid=False,
                reason="No validation rules configured"
            )

        # Parse allowed extensions
        try:
            allowed_extensions = json.loads(rules.allowed_extensions)
            allowed_extensions_lower = [ext.lower() for ext in allowed_extensions]
        except json.JSONDecodeError:
            return ValidationResult(
                is_valid=False,
                reason="Invalid allowed_extensions configuration"
            )

        # Validate each attachment
        total_size = 0

        for attachment in attachments:
            filename = attachment.get('filename', '')
            size = attachment.get('size', 0)

            # Get file extension
            file_path = Path(filename)
            extension = file_path.suffix.lower()

            # Check if file has extension
            if not extension:
                return ValidationResult(
                    is_valid=False,
                    reason=f"File '{filename}' has no extension",
                    details={'filename': filename}
                )

            # Check file type
            if extension not in allowed_extensions_lower:
                return ValidationResult(
                    is_valid=False,
                    reason=f"File type not allowed: {extension} (filename: {filename})",
                    details={
                        'filename': filename,
                        'extension': extension,
                        'allowed_extensions': allowed_extensions
                    }
                )

            # Check file size
            size_mb = size / (1024 * 1024)
            if size_mb > rules.max_file_size_mb:
                return ValidationResult(
                    is_valid=False,
                    reason=f"File '{filename}' too large: {size_mb:.1f} MB (max: {rules.max_file_size_mb} MB)",
                    details={
                        'filename': filename,
                        'size_mb': size_mb,
                        'max_mb': rules.max_file_size_mb
                    }
                )

            total_size += size

        # Check total size
        total_size_mb = total_size / (1024 * 1024)
        if total_size_mb > rules.max_total_size_mb:
            return ValidationResult(
                is_valid=False,
                reason=f"Total attachments size too large: {total_size_mb:.1f} MB (max: {rules.max_total_size_mb} MB)",
                details={
                    'total_size_mb': total_size_mb,
                    'max_mb': rules.max_total_size_mb
                }
            )

        # All validations passed
        return ValidationResult(is_valid=True)