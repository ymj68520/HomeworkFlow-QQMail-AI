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


@pytest.mark.asyncio
async def test_batch_retry_unknown_large_batch_splitting():
    """Test that batches larger than 20 are split into multiple API calls"""
    # Create 25 emails (should split into 2 batches: 20 + 5)
    email_list = [
        {
            'uid': f'{10000+i}',
            'subject': f'202100{i}学生{i}-作业1',
            'from': f'学生{i} <student{i}@example.com>',
            'attachments': [{'filename': 'file.pdf', 'content': b''}],
            'previous_result': {'student_id': None, 'name': None, 'assignment_name': None}
        }
        for i in range(25)
    ]

    extractor = AIExtractor()
    original_client = extractor.client

    # Track how many times the API is called
    call_count = [0]

    async def mock_create(*args, **kwargs):
        call_count[0] += 1
        batch_size = 20 if call_count[0] == 1 else 5

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]

        results = [
            {
                'is_assignment': True,
                'student_id': f'202100{i}',
                'name': f'学生{i}',
                'assignment_name': '作业1',
                'confidence': 0.8,
                'reasoning': 'Extracted'
            }
            for i in range(batch_size)
        ]

        mock_response.choices[0].message.content = json.dumps(results)
        return mock_response

    extractor.client = MagicMock()
    extractor.client.chat.completions.create = AsyncMock(side_effect=mock_create)

    try:
        result = await extractor.batch_retry_unknown(email_list)

        assert len(result) == 25
        assert call_count[0] == 2  # Should have made 2 API calls
    finally:
        extractor.client = original_client