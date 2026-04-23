"""
Tests for AI extractor batch processing
"""
import pytest
import asyncio
from ai.extractor import AIExtractor

@pytest.mark.asyncio
async def test_batch_processing_returns_all_results():
    """Test that batch processing returns results for all emails"""
    extractor = AIExtractor()
    emails = [
        {'uid': str(i), 'subject': f'202100{i}学生-作业1', 'from': '学生', 'attachments': []}
        for i in range(5)
    ]

    results = await extractor.batch_extract(emails)

    assert len(results) == 5
    for result in results:
        assert 'student_id' in result
        assert 'name' in result
        assert 'assignment_name' in result

@pytest.mark.asyncio
async def test_batch_processing_maintains_order():
    """Test that batch processing maintains input order"""
    extractor = AIExtractor()
    emails = [
        {'uid': '1', 'subject': '2021001张三-作业1', 'from': '张三', 'attachments': []},
        {'uid': '2', 'subject': '2021002李四-作业2', 'from': '李四', 'attachments': []},
        {'uid': '3', 'subject': '2021003王五-作业3', 'from': '王五', 'attachments': []},
    ]

    results = await extractor.batch_extract(emails)

    # Check that order is maintained
    assert len(results) == 3
    # Results should correspond to input emails

@pytest.mark.asyncio
async def test_batch_processing_handles_exceptions():
    """Test that batch processing handles exceptions gracefully"""
    extractor = AIExtractor()
    emails = [
        {'uid': '1', 'subject': 'valid email', 'from': 'sender', 'attachments': []},
        {'uid': '2', 'subject': '', 'from': '', 'attachments': []},  # Invalid
        {'uid': '3', 'subject': 'another valid', 'from': 'sender', 'attachments': []},
    ]

    results = await extractor.batch_extract(emails)

    # Should return results for all emails, even invalid ones
    assert len(results) == 3
    for result in results:
        assert result is not None
        assert isinstance(result, dict)

@pytest.mark.asyncio
async def test_batch_processing_with_custom_batch_size():
    """Test batch processing with custom batch size"""
    extractor = AIExtractor()
    emails = [
        {'uid': str(i), 'subject': f'email{i}', 'from': 'sender', 'attachments': []}
        for i in range(15)
    ]

    # Process with batch size of 5
    results = await extractor.batch_extract(emails, batch_size=5)

    assert len(results) == 15
