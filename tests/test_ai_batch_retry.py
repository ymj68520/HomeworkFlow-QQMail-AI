# tests/test_ai_batch_retry.py
"""Tests for AI batch retry functionality"""

import pytest
import json
from unittest.mock import MagicMock, AsyncMock
from ai.extractor import AIExtractor

@pytest.mark.asyncio
async def test_batch_retry_unknown_empty_list():
    """Test that batch_retry_unknown returns empty list for empty input"""
    extractor = AIExtractor()
    result = await extractor.batch_retry_unknown([])

    assert result == []


@pytest.mark.asyncio
async def test_batch_retry_unknown_single_email():
    """Test batch retry with single email"""
    email_list = [{
        'uid': '12345',
        'subject': '2021001张三-作业1',
        'from': '张三 <zhangsan@example.com>',
        'attachments': [{'filename': 'report.pdf', 'content': b''}],
        'previous_result': {
            'is_assignment': True,
            'student_id': None,
            'name': None,
            'assignment_name': None,
            'confidence': 0.3,
            'reasoning': 'Could not extract'
        }
    }]

    # Mock the AI client to avoid real API call
    extractor = AIExtractor()
    original_client = extractor.client

    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = json.dumps([{
        'is_assignment': True,
        'student_id': '2021001',
        'name': '张三',
        'assignment_name': '作业1',
        'confidence': 0.9,
        'reasoning': 'Successfully extracted from batch'
    }])

    extractor.client = MagicMock()
    extractor.client.chat.completions.create = AsyncMock(return_value=mock_response)

    try:
        result = await extractor.batch_retry_unknown(email_list)

        assert len(result) == 1
        assert result[0]['student_id'] == '2021001'
        assert result[0]['name'] == '张三'
        assert result[0]['assignment_name'] == '作业1'
        assert result[0]['confidence'] == 0.9
    finally:
        extractor.client = original_client


@pytest.mark.asyncio
async def test_batch_retry_unknown_multiple_emails():
    """Test batch retry with multiple emails"""
    email_list = [
        {
            'uid': '12345',
            'subject': '2021001张三-作业1',
            'from': '张三 <zhangsan@example.com>',
            'attachments': [{'filename': 'report.pdf', 'content': b''}],
            'previous_result': {'student_id': None, 'name': None, 'assignment_name': None}
        },
        {
            'uid': '12346',
            'subject': '2021002李四-作业2',
            'from': '李四 <lisi@example.com>',
            'attachments': [{'filename': 'homework.docx', 'content': b''}],
            'previous_result': {'student_id': None, 'name': None, 'assignment_name': None}
        }
    ]

    extractor = AIExtractor()
    original_client = extractor.client

    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = json.dumps([
        {
            'is_assignment': True,
            'student_id': '2021001',
            'name': '张三',
            'assignment_name': '作业1',
            'confidence': 0.9,
            'reasoning': 'Extracted'
        },
        {
            'is_assignment': True,
            'student_id': '2021002',
            'name': '李四',
            'assignment_name': '作业2',
            'confidence': 0.85,
            'reasoning': 'Extracted'
        }
    ])

    extractor.client = MagicMock()
    extractor.client.chat.completions.create = AsyncMock(return_value=mock_response)

    try:
        result = await extractor.batch_retry_unknown(email_list)

        assert len(result) == 2
        assert result[0]['student_id'] == '2021001'
        assert result[1]['student_id'] == '2021002'
    finally:
        extractor.client = original_client