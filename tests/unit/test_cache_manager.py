"""测试CacheManager"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

import pytest
from unittest.mock import Mock, AsyncMock
from core.deduplication.cache_manager import CacheManager


@pytest.fixture
def mock_db():
    """模拟数据库操作"""
    db = Mock()
    db.get_ai_cache = AsyncMock()
    db.save_ai_cache = AsyncMock()
    return db


@pytest.fixture
def cache_manager(mock_db):
    """创建CacheManager实例"""
    return CacheManager(mock_db)


@pytest.mark.asyncio
async def test_get_returns_cached_data(cache_manager, mock_db):
    """测试：缓存命中返回存储的数据"""
    cached_data = {
        'student_id': 'S001',
        'name': '张三',
        'assignment_name': '作业1',
        'confidence': 0.95
    }
    mock_db.get_ai_cache.return_value = cached_data

    result = await cache_manager.get("test_uid")

    assert result == cached_data
    mock_db.get_ai_cache.assert_called_once_with("test_uid")


@pytest.mark.asyncio
async def test_get_returns_none_when_cache_miss(cache_manager, mock_db):
    """测试：缓存未命中返回None"""
    mock_db.get_ai_cache.return_value = None

    result = await cache_manager.get("test_uid")

    assert result is None


@pytest.mark.asyncio
async def test_set_saves_to_cache(cache_manager, mock_db):
    """测试：保存数据到缓存"""
    result_data = {
        'student_id': 'S001',
        'name': '张三',
        'assignment_name': '作业1',
        'confidence': 0.95
    }

    await cache_manager.set("test_uid", result_data, is_fallback=False)

    mock_db.save_ai_cache.assert_called_once_with(
        "test_uid", result_data, False
    )


@pytest.mark.asyncio
async def test_set_with_fallback_flag(cache_manager, mock_db):
    """测试：保存数据到缓存（标记为fallback）"""
    result_data = {
        'student_id': 'S001',
        'name': '张三',
        'assignment_name': '作业1'
    }

    await cache_manager.set("test_uid", result_data, is_fallback=True)

    mock_db.save_ai_cache.assert_called_once_with(
        "test_uid", result_data, True
    )


@pytest.mark.asyncio
async def test_has_cache_returns_true_when_exists(cache_manager, mock_db):
    """测试：检查缓存存在时返回True"""
    mock_db.get_ai_cache.return_value = {'student_id': 'S001'}

    result = await cache_manager.has("test_uid")

    assert result is True


@pytest.mark.asyncio
async def test_has_cache_returns_false_when_not_exists(cache_manager, mock_db):
    """测试：检查缓存不存在时返回False"""
    mock_db.get_ai_cache.return_value = None

    result = await cache_manager.has("test_uid")

    assert result is False
