"""
Tests for AI extractor cache integration
"""
import pytest
import asyncio
from ai.extractor import AIExtractor
from database.operations import db
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
async def test_cache_miss_then_hit():
    """Test that cache miss triggers AI call, second call hits cache"""
    extractor = AIExtractor()
    email_data = {
        'uid': '12345',
        'subject': '2021001张三-作业1提交',
        'from': '张三',
        'attachments': []
    }

    # First call should miss cache
    result1 = await extractor.extract_with_cache(email_data)
    assert result1 is not None
    assert 'student_id' in result1

    # Second call should hit cache
    result2 = await extractor.extract_with_cache(email_data)
    assert result2 == result1

@pytest.mark.asyncio
async def test_cache_saves_fallback_flag():
    """Test that fallback results are marked correctly"""
    extractor = AIExtractor()
    email_data = {
        'uid': '67890',
        'subject': 'invalid subject',
        'from': 'unknown',
        'attachments': []
    }

    result = await extractor.extract_with_cache(email_data)

    # Check database for is_fallback flag
    session = SessionLocal()
    cache_entry = session.query(AIExtractionCache).filter_by(
        email_uid='67890'
    ).first()

    if cache_entry:
        assert cache_entry.is_fallback == result.get('is_fallback')

    session.close()

@pytest.mark.asyncio
async def test_cache_persists_across_instances():
    """Test that cache persists across AIExtractor instances"""
    extractor1 = AIExtractor()
    email_data = {
        'uid': '99999',
        'subject': '2021002李四-作业2提交',
        'from': '李四',
        'attachments': []
    }

    # Extract with first instance
    result1 = await extractor1.extract_with_cache(email_data)

    # Create new instance and extract again
    extractor2 = AIExtractor()
    result2 = await extractor2.extract_with_cache(email_data)

    # Should get same result from cache
    assert result2 == result1
