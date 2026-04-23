# tests/test_ai_batch_retry.py
"""Tests for AI batch retry functionality"""

import pytest
from ai.extractor import AIExtractor

@pytest.mark.asyncio
async def test_batch_retry_unknown_empty_list():
    """Test that batch_retry_unknown returns empty list for empty input"""
    extractor = AIExtractor()
    result = await extractor.batch_retry_unknown([])

    assert result == []