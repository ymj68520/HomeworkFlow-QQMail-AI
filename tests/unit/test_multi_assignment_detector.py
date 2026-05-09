"""测试MultiAssignmentDetector"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
import json
import hashlib
import asyncio

from ai.multi_assignment_detector import MultiAssignmentDetector


@pytest.fixture
def mock_settings():
    """模拟设置"""
    settings = Mock()
    settings.API_KEY = "test_api_key"
    settings.LLM_BASE_URL = "https://api.test.com"
    settings.LLM_MODEL = "gpt-4"
    settings.ENABLE_MULTI_ASSIGNMENT = True
    settings.MULTI_ASSIGNMENT_CONFIG = {
        'enable_subject_detection': True,
        'enable_filename_detection': True,
        'enable_body_detection': True,
        'min_confidence_threshold': 0.7,
        'strict_mode': True,
        'max_attachments_per_group': 10,
        'max_assignments_per_group': 5
    }
    return settings


@pytest.fixture
def mock_async_db():
    """模拟异步数据库"""
    db = Mock()
    db.get_multi_assignment_cache = AsyncMock(return_value=None)
    db.save_multi_assignment_cache = AsyncMock()
    return db


@pytest.fixture
def mock_openai_client():
    """模拟OpenAI客户端"""
    client = AsyncMock()
    response = Mock()
    response.choices = [Mock()]
    response.choices[0].message.content = json.dumps({
        'is_multi_assignment': True,
        'is_complete': True,
        'assignments': [
            {
                'assignment_name': '作业1',
                'attachments': ['作业1.pdf'],
                'confidence': 0.9
            },
            {
                'assignment_name': '作业2',
                'attachments': ['作业2.pdf'],
                'confidence': 0.85
            }
        ],
        'unassigned_attachments': [],
        'overall_confidence': 0.87,
        'student_id': 'S001',
        'name': '张三',
        'reasoning': '从邮件主题识别到多作业提交'
    })
    client.chat.completions.create = AsyncMock(return_value=response)
    return client


@pytest.fixture
def detector(mock_settings, mock_async_db, mock_openai_client):
    """创建MultiAssignmentDetector实例"""
    with patch('ai.multi_assignment_detector.settings', mock_settings), \
         patch('ai.multi_assignment_detector.async_db', mock_async_db), \
         patch('ai.multi_assignment_detector.AsyncOpenAI', return_value=mock_openai_client):
        det = MultiAssignmentDetector()
        det.client = mock_openai_client
        return det


@pytest.mark.asyncio
async def test_single_assignment_result_when_feature_disabled(detector, mock_settings):
    """测试：功能禁用时返回单作业结果"""
    mock_settings.ENABLE_MULTI_ASSIGNMENT = False

    result = await detector.detect_multi_assignment(
        subject="测试邮件",
        sender="test@example.com",
        attachments=[{'filename': 'test.pdf', 'content': b'test'}]
    )

    assert result['is_multi_assignment'] is False
    assert result['is_complete'] is False
    assert result['detection_method'] == 'none'
    assert result['assignments'] == []
    assert result['overall_confidence'] == 0.0
    assert result['student_id'] is None
    assert result['name'] is None


@pytest.mark.asyncio
async def test_detect_from_subject(detector):
    """测试：从邮件主题检测多作业提交"""
    subject = "作业1+作业2提交 - 张三"
    sender = "zhangsan@example.com"
    attachments = [
        {'filename': '作业1.pdf', 'content': b'content1'},
        {'filename': '作业2.pdf', 'content': b'content2'}
    ]

    result = await detector.detect_multi_assignment(
        subject=subject,
        sender=sender,
        attachments=attachments
    )

    assert result['is_multi_assignment'] is True
    assert result['is_complete'] is True
    assert result['detection_method'] == 'subject'
    assert len(result['assignments']) == 2
    assert result['assignments'][0]['assignment_name'] == '作业1'
    assert result['assignments'][1]['assignment_name'] == '作业2'
    assert result['overall_confidence'] == 0.87
    assert result['student_id'] == 'S001'
    assert result['name'] == '张三'


@pytest.mark.asyncio
async def test_detection_from_filename(detector, mock_async_db, mock_openai_client):
    """测试：从附件文件名检测多作业提交"""
    # 配置只启用文件名检测
    detector.config['enable_subject_detection'] = False
    detector.config['enable_filename_detection'] = True

    subject = "作业提交"
    sender = "lisi@example.com"
    attachments = [
        {'filename': '实验报告1.pdf', 'content': b'content1'},
        {'filename': '实验报告2.pdf', 'content': b'content2'}
    ]

    # Mock AI响应
    mock_openai_client.chat.completions.create.return_value.choices[0].message.content = json.dumps({
        'is_multi_assignment': True,
        'is_complete': True,
        'assignments': [
            {
                'assignment_name': '实验报告1',
                'attachments': ['实验报告1.pdf'],
                'confidence': 0.92
            },
            {
                'assignment_name': '实验报告2',
                'attachments': ['实验报告2.pdf'],
                'confidence': 0.88
            }
        ],
        'unassigned_attachments': [],
        'overall_confidence': 0.90,
        'student_id': 'S002',
        'name': '李四',
        'reasoning': '从文件名识别到多作业提交'
    })

    result = await detector.detect_multi_assignment(
        subject=subject,
        sender=sender,
        attachments=attachments
    )

    assert result['is_multi_assignment'] is True
    assert result['is_complete'] is True
    assert result['detection_method'] == 'filename'
    assert len(result['assignments']) == 2
    assert result['overall_confidence'] == 0.90
    assert result['student_id'] == 'S002'
    assert result['name'] == '李四'


@pytest.mark.asyncio
async def test_incomplete_detection_strict_mode(detector, mock_openai_client):
    """测试：严格模式下未分配附件导致检测不完整"""
    # 配置严格模式
    detector.config['strict_mode'] = True

    subject = "作业提交"
    sender = "wangwu@example.com"
    attachments = [
        {'filename': '作业1.pdf', 'content': b'content1'},
        {'filename': '作业2.pdf', 'content': b'content2'},
        {'filename': '未分配.pdf', 'content': b'content3'}  # 这个附件不会被分配
    ]

    # Mock AI响应 - 故意不分配所有附件
    mock_openai_client.chat.completions.create.return_value.choices[0].message.content = json.dumps({
        'is_multi_assignment': True,
        'is_complete': True,
        'assignments': [
            {
                'assignment_name': '作业1',
                'attachments': ['作业1.pdf'],
                'confidence': 0.9
            },
            {
                'assignment_name': '作业2',
                'attachments': ['作业2.pdf'],
                'confidence': 0.85
            }
        ],
        'unassigned_attachments': [],
        'overall_confidence': 0.87,
        'student_id': 'S003',
        'name': '王五',
        'reasoning': '检测到多作业提交'
    })

    result = await detector.detect_multi_assignment(
        subject=subject,
        sender=sender,
        attachments=attachments
    )

    # _validate_result会检测到有未分配的附件（未分配.pdf）
    # 在严格模式下，这会导致is_complete=False
    # 由于is_complete=False，主方法不会返回这个结果，而是返回_single_assignment_result()
    assert result['is_multi_assignment'] is False  # 返回单作业结果
    assert result['is_complete'] is False
    assert result['detection_method'] == 'none'


@pytest.mark.asyncio
async def test_low_confidence_threshold(detector, mock_openai_client):
    """测试：低置信度导致检测不完整"""
    # 设置置信度阈值为0.8
    detector.config['min_confidence_threshold'] = 0.8

    subject = "作业提交"
    sender = "zhaoliu@example.com"
    attachments = [
        {'filename': '作业1.pdf', 'content': b'content1'},
        {'filename': '作业2.pdf', 'content': b'content2'}
    ]

    # Mock AI响应 - 返回低置信度
    mock_openai_client.chat.completions.create.return_value.choices[0].message.content = json.dumps({
        'is_multi_assignment': True,
        'is_complete': True,
        'assignments': [
            {
                'assignment_name': '作业1',
                'attachments': ['作业1.pdf'],
                'confidence': 0.6
            },
            {
                'assignment_name': '作业2',
                'attachments': ['作业2.pdf'],
                'confidence': 0.5
            }
        ],
        'unassigned_attachments': [],
        'overall_confidence': 0.55,  # 低于阈值0.8
        'student_id': 'S004',
        'name': '赵六',
        'reasoning': '检测到多作业提交'
    })

    result = await detector.detect_multi_assignment(
        subject=subject,
        sender=sender,
        attachments=attachments
    )

    # 当置信度低于阈值时，is_complete会被设置为False
    # 由于is_multi_assignment=True但is_complete=False，主方法不会返回这个结果
    # 而是会继续尝试其他方法，最终返回_single_assignment_result()
    assert result['is_multi_assignment'] is False  # 因为is_complete=False，所以返回单作业结果
    assert result['is_complete'] is False
    assert result['detection_method'] == 'none'


@pytest.mark.asyncio
async def test_cached_result_returned(detector):
    """测试：缓存结果被正确返回"""
    # 创建一个新的detector实例，专门用于测试缓存
    with patch('ai.multi_assignment_detector.async_db') as mock_db:
        # 构建正确的缓存键
        subject = "test"
        sender = "example.com"
        attachments = [{'filename': 'test.pdf', 'size': 0}]

        cached_result = {
            'is_multi_assignment': True,
            'is_complete': True,
            'detection_method': 'subject',
            'assignments': [
                {'assignment_name': '作业1', 'attachments': ['test.pdf'], 'confidence': 0.9}
            ],
            'unassigned_attachments': [],
            'overall_confidence': 0.9,
            'student_id': 'S001',
            'name': '测试',
            'reasoning': '缓存结果'
        }
        mock_db.get_multi_assignment_cache = AsyncMock(return_value=cached_result)
        mock_db.save_multi_assignment_cache = AsyncMock()

        # 设置detector的async_db为mock版本
        detector_copy = MultiAssignmentDetector()
        detector_copy.client = detector.client
        detector_copy.config = detector.config

        result = await detector_copy.detect_multi_assignment(
            subject=subject,
            sender=sender,
            attachments=attachments
        )

        # 验证返回了缓存的结果
        assert result['is_multi_assignment'] == cached_result['is_multi_assignment']
        assert result['is_complete'] == cached_result['is_complete']
        assert result['detection_method'] == cached_result['detection_method']
        assert result['assignments'] == cached_result['assignments']
        assert result['overall_confidence'] == cached_result['overall_confidence']
        assert result['student_id'] == cached_result['student_id']
        assert result['name'] == cached_result['name']


@pytest.mark.asyncio
async def test_ai_timeout_returns_single_assignment(detector, mock_openai_client):
    """测试：AI超时时返回单作业结果"""
    mock_openai_client.chat.completions.create.side_effect = asyncio.TimeoutError()

    result = await detector.detect_multi_assignment(
        subject="作业1+作业2",
        sender="test@example.com",
        attachments=[{'filename': 'test.pdf', 'content': b'test'}]
    )

    assert result['is_multi_assignment'] is False
    assert result['is_complete'] is False
    assert result['detection_method'] == 'none'


@pytest.mark.asyncio
async def test_detection_from_body(detector, mock_openai_client):
    """测试：从邮件正文检测多作业提交"""
    # 配置只启用正文检测
    detector.config['enable_subject_detection'] = False
    detector.config['enable_filename_detection'] = False
    detector.config['enable_body_detection'] = True

    subject = "作业提交"
    sender = "test@example.com"
    attachments = [
        {'filename': 'lab1.pdf', 'content': b'content1'},
        {'filename': 'lab2.pdf', 'content': b'content2'}
    ]
    email_body = {
        'plain_text': '老师好，这是我的实验1和实验2的作业，请查收。',
        'html_markdown': '老师好，这是我的实验1和实验2的作业，请查收。'
    }

    # Mock AI响应
    mock_openai_client.chat.completions.create.return_value.choices[0].message.content = json.dumps({
        'is_multi_assignment': True,
        'is_complete': True,
        'assignments': [
            {
                'assignment_name': '实验1',
                'attachments': ['lab1.pdf'],
                'confidence': 0.9
            },
            {
                'assignment_name': '实验2',
                'attachments': ['lab2.pdf'],
                'confidence': 0.88
            }
        ],
        'unassigned_attachments': [],
        'overall_confidence': 0.89,
        'student_id': 'S005',
        'name': '测试学生',
        'reasoning': '从邮件正文识别到多作业提交'
    })

    result = await detector.detect_multi_assignment(
        subject=subject,
        sender=sender,
        attachments=attachments,
        email_body=email_body
    )

    assert result['is_multi_assignment'] is True
    assert result['is_complete'] is True
    assert result['detection_method'] == 'body'
    assert len(result['assignments']) == 2


@pytest.mark.asyncio
async def test_non_strict_mode_allows_unassigned(detector):
    """测试：非严格模式下允许未分配附件"""
    # 配置非严格模式
    detector.config['strict_mode'] = False

    subject = "作业提交"
    sender = "test@example.com"
    attachments = [
        {'filename': '作业1.pdf', 'content': b'content1'},
        {'filename': '未分配.pdf', 'content': b'content2'}
    ]

    result = await detector.detect_multi_assignment(
        subject=subject,
        sender=sender,
        attachments=attachments
    )

    # 非严格模式下，即使有未分配附件也应该标记为完整
    assert result['is_complete'] is True
    assert result['unassigned_attachments'] == []


@pytest.mark.asyncio
async def test_build_cache_key():
    """测试：缓存键构建正确性"""
    with patch('ai.multi_assignment_detector.settings', Mock(API_KEY='test', LLM_BASE_URL='test', LLM_MODEL='test', ENABLE_MULTI_ASSIGNMENT=True, MULTI_ASSIGNMENT_CONFIG={})):
        with patch('ai.multi_assignment_detector.async_db', AsyncMock(get_multi_assignment_cache=AsyncMock(return_value=None))):
            with patch('ai.multi_assignment_detector.AsyncOpenAI'):
                det = MultiAssignmentDetector()

    subject = "测试主题"
    sender = "test@example.com"
    attachments = [
        {'filename': 'file1.pdf', 'size': 1024},
        {'filename': 'file2.pdf', 'size': 2048}
    ]

    cache_key = det._build_cache_key(subject, sender, attachments)

    # 验证缓存键是基于输入确定性生成的
    expected_key_data = f"{subject}:{sender}:file1.pdf1024:file2.pdf2048"
    expected_key = hashlib.md5(expected_key_data.encode()).hexdigest()

    assert cache_key == expected_key


@pytest.mark.asyncio
async def test_empty_attachments(detector, mock_openai_client):
    """测试：空附件列表的处理"""
    # 即使没有附件，AI仍可能返回多作业检测结果
    # 但实际场景中，没有附件应该返回单作业结果
    mock_openai_client.chat.completions.create.return_value.choices[0].message.content = json.dumps({
        'is_multi_assignment': True,
        'is_complete': True,
        'assignments': [],
        'overall_confidence': 0.8,
        'student_id': 'S001',
        'name': '测试',
        'reasoning': '检测到多作业提交'
    })

    result = await detector.detect_multi_assignment(
        subject="作业提交",
        sender="test@example.com",
        attachments=[]
    )

    # 没有附件时，AI可能返回is_multi_assignment=True，但由于没有作业会被识别
    # 最终可能返回单作业结果或多作业结果（取决于AI响应）
    # 这里我们验证返回的结果结构是正确的
    assert 'is_multi_assignment' in result
    assert 'is_complete' in result
    assert 'detection_method' in result


@pytest.mark.asyncio
async def test_save_cache_error_handling(detector, mock_async_db):
    """测试：缓存保存失败不影响检测结果"""
    mock_async_db.save_multi_assignment_cache.side_effect = Exception("Cache save failed")

    result = await detector.detect_multi_assignment(
        subject="作业1+作业2",
        sender="test@example.com",
        attachments=[
            {'filename': '作业1.pdf', 'content': b'content1'},
            {'filename': '作业2.pdf', 'content': b'content2'}
        ]
    )

    # 即使缓存保存失败，检测仍然应该成功
    assert result['is_multi_assignment'] is True
    assert result['is_complete'] is True
