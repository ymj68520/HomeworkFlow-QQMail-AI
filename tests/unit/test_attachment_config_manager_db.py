# tests/unit/test_attachment_config_manager_db.py
import pytest
import asyncio
from core.attachment_config_manager import AttachmentConfigManager
from database.async_operations import AsyncDatabaseOperations

@pytest.mark.asyncio
async def test_get_current_rules():
    """Test getting current active rules from database"""
    manager = AttachmentConfigManager()
    rules = await manager.get_current_rules()

    assert rules is not None
    assert rules.rule_name == 'default'
    assert rules.is_active is True
    assert rules.max_file_size_mb == 25.0

@pytest.mark.asyncio
async def test_update_rules():
    """Test updating rules in database"""
    manager = AttachmentConfigManager()

    # Update rules
    success = await manager.update_rules(
        allowed_extensions=['.pdf', '.txt'],
        max_file_size_mb=50.0,
        max_total_size_mb=200.0
    )

    assert success is True

    # Verify update
    rules = await manager.get_current_rules()
    assert '.pdf' in rules.allowed_extensions
    assert '.txt' in rules.allowed_extensions
    # Restore defaults
    await manager.update_rules(
        allowed_extensions=['.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx', '.txt', '.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp', '.zip', '.rar', '.7z', '.tar', '.gz'],
        max_file_size_mb=25.0,
        max_total_size_mb=100.0
    )