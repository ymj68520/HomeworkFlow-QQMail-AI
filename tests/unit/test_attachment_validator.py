# tests/unit/test_attachment_validator.py
import pytest
from unittest.mock import AsyncMock, MagicMock
from core.attachment_validator import AttachmentValidator
from core.validation_result import ValidationResult

@pytest.fixture
def mock_config_manager():
    """Create a mock config manager"""
    manager = AsyncMock()
    manager.get_current_rules.return_value = MagicMock(
        allowed_extensions='[".pdf", ".doc", ".docx", ".png", ".jpg", ".zip"]',
        max_file_size_mb=25.0,
        max_total_size_mb=100.0
    )
    return manager

@pytest.fixture
def mock_config_manager_large_files():
    """Create a mock config manager that allows larger files for testing total size"""
    manager = AsyncMock()
    manager.get_current_rules.return_value = MagicMock(
        allowed_extensions='[".pdf", ".doc", ".docx", ".png", ".jpg", ".zip"]',
        max_file_size_mb=40.0,  # Allow files up to 40MB
        max_total_size_mb=100.0
    )
    return manager

@pytest.mark.asyncio
async def test_validate_all_valid(mock_config_manager):
    """Test validation with all valid attachments"""
    validator = AttachmentValidator(mock_config_manager)

    attachments = [
        {'filename': 'document.pdf', 'content': b'...', 'size': 10 * 1024 * 1024},  # 10MB
        {'filename': 'image.png', 'content': b'...', 'size': 5 * 1024 * 1024},     # 5MB
    ]

    result = await validator.validate_attachments(attachments)

    assert result.is_valid is True
    assert result.reason is None

@pytest.mark.asyncio
async def test_validate_invalid_file_type(mock_config_manager):
    """Test validation with invalid file type"""
    validator = AttachmentValidator(mock_config_manager)

    attachments = [
        {'filename': 'document.pdf', 'content': b'...', 'size': 10 * 1024 * 1024},
        {'filename': 'virus.exe', 'content': b'...', 'size': 1 * 1024 * 1024},  # Invalid type
    ]

    result = await validator.validate_attachments(attachments)

    assert result.is_valid is False
    assert 'virus.exe' in result.reason
    assert '.exe' in result.reason

@pytest.mark.asyncio
async def test_validate_file_too_large(mock_config_manager):
    """Test validation with file exceeding size limit"""
    validator = AttachmentValidator(mock_config_manager)

    attachments = [
        {'filename': 'huge.pdf', 'content': b'...', 'size': 30 * 1024 * 1024},  # 30MB > 25MB
    ]

    result = await validator.validate_attachments(attachments)

    assert result.is_valid is False
    assert 'huge.pdf' in result.reason
    assert '30.0 MB' in result.reason
    assert '25.0 MB' in result.reason

@pytest.mark.asyncio
async def test_validate_total_size_exceeded(mock_config_manager_large_files):
    """Test validation with total size exceeding limit"""
    validator = AttachmentValidator(mock_config_manager_large_files)

    attachments = [
        {'filename': 'file1.pdf', 'content': b'...', 'size': 35 * 1024 * 1024},  # 35MB (< 40MB limit)
        {'filename': 'file2.pdf', 'content': b'...', 'size': 35 * 1024 * 1024},  # 35MB (< 40MB limit)
        {'filename': 'file3.pdf', 'content': b'...', 'size': 35 * 1024 * 1024},  # 35MB (< 40MB limit)
        # Total: 105MB > 100MB
    ]

    result = await validator.validate_attachments(attachments)

    assert result.is_valid is False
    assert 'total attachments' in result.reason.lower()
    assert '105.0 MB' in result.reason
    assert '100.0 MB' in result.reason

@pytest.mark.asyncio
async def test_validate_case_insensitive_extension(mock_config_manager):
    """Test that extension matching is case-insensitive"""
    validator = AttachmentValidator(mock_config_manager)

    attachments = [
        {'filename': 'document.PDF', 'content': b'...', 'size': 1 * 1024 * 1024},
        {'filename': 'image.PNG', 'content': b'...', 'size': 1 * 1024 * 1024},
        {'filename': 'archive.ZIP', 'content': b'...', 'size': 1 * 1024 * 1024},
    ]

    result = await validator.validate_attachments(attachments)

    assert result.is_valid is True

@pytest.mark.asyncio
async def test_validate_no_extensions(mock_config_manager):
    """Test file with no extension"""
    validator = AttachmentValidator(mock_config_manager)

    attachments = [
        {'filename': 'README', 'content': b'...', 'size': 1 * 1024},
    ]

    result = await validator.validate_attachments(attachments)

    assert result.is_valid is False
    assert 'README' in result.reason
    assert 'no extension' in result.reason.lower()