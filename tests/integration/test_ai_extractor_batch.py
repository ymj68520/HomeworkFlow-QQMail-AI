"""
Tests for AI extractor batch processing
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, patch
from ai.extractor import AIExtractor
from database.models import SessionLocal, AIExtractionCache

@pytest.fixture(autouse=True)
def clear_cache():
    """Clear cache before each test to ensure test isolation"""
    session = SessionLocal()
    session.query(AIExtractionCache).delete()
    session.commit()
    session.close()
    yield
    # Cleanup after test
    session = SessionLocal()
    session.query(AIExtractionCache).delete()
    session.commit()
    session.close()

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

    # Verify that results correspond to input emails in order
    assert results[0]['student_id'] == '2021001'
    assert results[0]['name'] == '张三'
    assert results[0]['assignment_name'] == '作业1'

    assert results[1]['student_id'] == '2021002'
    assert results[1]['name'] == '李四'
    assert results[1]['assignment_name'] == '作业2'

    assert results[2]['student_id'] == '2021003'
    assert results[2]['name'] == '王五'
    assert results[2]['assignment_name'] == '作业3'

@pytest.mark.asyncio
async def test_batch_processing_handles_exceptions():
    """Test that batch processing handles exceptions gracefully"""
    extractor = AIExtractor()

    # Mock extract_with_cache to raise exceptions for specific emails
    async def mock_extract_with_exception(email_data):
        if email_data['uid'] == '2':
            raise ValueError("Simulated extraction error")
        # Return valid result for other emails
        return {
            'student_id': '2021000',
            'name': 'Test',
            'assignment_name': '作业1',
            'is_fallback': False,
            'confidence': 0.9
        }

    # Patch the extract_with_cache method
    with patch.object(extractor, 'extract_with_cache', side_effect=mock_extract_with_exception):
        emails = [
            {'uid': '1', 'subject': 'valid email', 'from': 'sender', 'attachments': []},
            {'uid': '2', 'subject': 'error email', 'from': 'sender', 'attachments': []},
            {'uid': '3', 'subject': 'another valid', 'from': 'sender', 'attachments': []},
        ]

        results = await extractor.batch_extract(emails)

        # Should return results for all emails, with fallback for exception
        assert len(results) == 3

        # First and third should have normal results
        assert results[0]['student_id'] == '2021000'
        assert results[2]['student_id'] == '2021000'

        # Second should have fallback result due to exception
        assert results[1]['student_id'] is None
        assert results[1]['name'] is None
        assert results[1]['is_fallback'] == True
        assert results[1]['confidence'] == 0.0

@pytest.mark.asyncio
async def test_batch_processing_with_custom_batch_size():
    """Test batch processing with custom batch size"""
    extractor = AIExtractor()

    # Track batch processing calls
    batch_calls = []

    original_extract = extractor.extract_with_cache

    async def tracked_extract(email_data):
        batch_calls.append(email_data['uid'])
        return await original_extract(email_data)

    with patch.object(extractor, 'extract_with_cache', side_effect=tracked_extract):
        emails = [
            {'uid': str(i), 'subject': f'202100{i}学生-作业1', 'from': '学生', 'attachments': []}
            for i in range(15)
        ]

        # Process with batch size of 5
        results = await extractor.batch_extract(emails, batch_size=5)

        # Verify all results returned
        assert len(results) == 15

        # Verify all emails were processed
        assert len(batch_calls) == 15

        # Verify results contain extracted data
        for result in results:
            assert 'student_id' in result
            assert 'name' in result
            assert 'assignment_name' in result
