"""测试事务性文件操作"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

import pytest
import tempfile
from pathlib import Path
from core.transactions.file_operations import TransactionalFileOperation
from core.transactions.recovery import RecoveryManager
from core.deduplication.models import FileOperationError


@pytest.fixture
def temp_dir():
    """创建临时目录"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.mark.asyncio
async def test_create_folder_success(temp_dir):
    """测试：成功创建文件夹"""
    file_op = TransactionalFileOperation(submission_id=1)
    test_path = temp_dir / "test_folder"

    result = await file_op.create_folder(test_path)

    assert result is True
    assert test_path.exists()
    assert ('create_folder', test_path) in file_op.operations
    await file_op.cleanup()


@pytest.mark.asyncio
async def test_save_file_success(temp_dir):
    """测试：成功保存文件"""
    file_op = TransactionalFileOperation(submission_id=1)
    test_path = temp_dir / "test_file.txt"
    content = b"test content"

    result = await file_op.save_file(test_path, content)

    assert result is True
    assert test_path.exists()
    assert test_path.read_bytes() == content
    await file_op.cleanup()


@pytest.mark.asyncio
async def test_save_file_creates_parent_dir(temp_dir):
    """测试：保存文件时自动创建父目录"""
    file_op = TransactionalFileOperation(submission_id=1)
    test_path = temp_dir / "subdir" / "test_file.txt"
    content = b"test content"

    result = await file_op.save_file(test_path, content)

    assert result is True
    assert test_path.exists()
    assert test_path.parent.exists()
    await file_op.cleanup()


@pytest.mark.asyncio
async def test_rollback_on_failure(temp_dir):
    """测试：失败时回滚已创建的文件"""
    file_op = TransactionalFileOperation(submission_id=1)

    # 创建第一个文件
    file1 = temp_dir / "file1.txt"
    await file_op.save_file(file1, b"content1")

    # 模拟数据库操作失败的情况
    # 通过创建一个无效路径来模拟失败
    # Windows上不能创建包含某些字符的文件名
    file2 = temp_dir / "file2.txt"

    # 手动触发回滚
    await file_op._rollback()

    # 验证回滚：第一个文件应该被删除
    assert not file1.exists()
    await file_op.cleanup()
