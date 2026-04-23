"""
Tests for AI extractor functionality
"""
import pytest
from ai.extractor import ai_extractor
from database.models import SessionLocal, AIExtractionCache

@pytest.fixture(autouse=True)
def clear_cache():
    """Clear cache before each test"""
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
async def test_extract_with_cache():
    """Test extraction with cache enabled"""
    email_data = {
        'uid': '12345',
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
        'uid': '67890',
        'subject': '2021002李四-作业2',
        'from': '李四',
        'attachments': []
    }

    result = await ai_extractor.extract_with_cache(email_data, use_cache=False)

    assert result is not None
    assert 'student_id' in result
    assert 'name' in result
    assert 'assignment_name' in result
    assert 'is_fallback' in result
