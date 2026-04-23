"""
Tests for AI extractor functionality
"""
import pytest
from ai.extractor import ai_extractor

@pytest.mark.asyncio
async def test_extract_with_cache():
    """Test extraction with cache enabled"""
    email_data = {
        'uid': 'test123',
        'subject': '2021001张三-作业1',
        'from': '张三',
        'attachments': []
    }

    result = await ai_extractor.extract_with_cache(email_data)

    assert result is not None
    assert 'student_id' in result
    assert 'name' in result
    assert 'assignment_name' in result
    assert 'is_fallback' in result

@pytest.mark.asyncio
async def test_extract_without_cache():
    """Test extraction with cache disabled"""
    email_data = {
        'uid': 'test456',
        'subject': '2021002李四-作业2',
        'from': '李四',
        'attachments': []
    }

    result = await ai_extractor.extract_with_cache(email_data, use_cache=False)

    assert result is not None
    assert 'student_id' in result
