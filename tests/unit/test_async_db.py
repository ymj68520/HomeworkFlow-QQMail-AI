"""测试异步数据库操作"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

import pytest
import asyncio
from database.async_operations import async_db


@pytest.mark.asyncio
async def test_get_submission_by_uid():
    """测试异步获取提交记录"""
    # 使用真实的email_uid测试
    result = await async_db.get_submission_by_uid("nonexistent_uid")
    assert result is None  # 不存在的记录应返回None


@pytest.mark.asyncio
async def test_get_latest_submission():
    """测试异步获取最新提交"""
    result = await async_db.get_latest_submission("S001", "作业1")
    # 可能返回None（如果没有数据）或返回Submission对象
    assert result is None or hasattr(result, 'id')


@pytest.mark.asyncio
async def test_get_ai_cache():
    """测试异步获取AI缓存"""
    result = await async_db.get_ai_cache("test_uid")
    assert result is None  # 不存在的缓存应返回None


@pytest.mark.asyncio
async def test_save_ai_cache():
    """测试异步保存AI缓存"""
    test_data = {
        'student_id': 'TEST001',
        'name': '测试学生',
        'assignment_name': '测试作业',
        'confidence': 0.95
    }

    # 保存缓存
    await async_db.save_ai_cache("test_async_uid", test_data)

    # 读取缓存
    result = await async_db.get_ai_cache("test_async_uid")

    assert result is not None
    assert result['student_id'] == 'TEST001'
    assert result['name'] == '测试学生'


if __name__ == "__main__":
    # 简单测试运行
    async def run_tests():
        print("Testing async database operations...")

        await test_get_submission_by_uid()
        print("[OK] test_get_submission_by_uid passed")

        await test_get_latest_submission()
        print("[OK] test_get_latest_submission passed")

        await test_get_ai_cache()
        print("[OK] test_get_ai_cache passed")

        await test_save_ai_cache()
        print("[OK] test_save_ai_cache passed")

        print("\nAll tests passed!")

    asyncio.run(run_tests())
