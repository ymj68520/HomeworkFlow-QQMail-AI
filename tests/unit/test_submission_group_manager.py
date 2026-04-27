"""测试SubmissionGroupManager"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

import pytest
from unittest.mock import Mock, AsyncMock, MagicMock, patch
from core.deduplication.submission_group_manager import SubmissionGroupManager
from database.models import Submission, RelationType


@pytest.fixture
def mock_db():
    """模拟异步数据库操作"""
    db = Mock()
    db.get_latest_submission = AsyncMock()
    return db


@pytest.fixture
def group_manager(mock_db):
    """创建SubmissionGroupManager实例"""
    return SubmissionGroupManager(mock_db)


@pytest.fixture
def mock_primary_submission():
    """创建主记录的模拟提交"""
    return Submission(
        id=1,
        student_id=1,
        assignment_id=1,
        version=2,
        is_latest=True,
        is_primary=True,
        parent_id=None,
        relation_type=None
    )


@pytest.fixture
def mock_child_submission():
    """创建子记录的模拟提交"""
    return Submission(
        id=2,
        student_id=1,
        assignment_id=1,
        version=1,
        is_latest=False,
        is_primary=False,
        parent_id=1,
        relation_type=RelationType.VERSION.value
    )


@pytest.fixture
def mock_orphan_submission():
    """创建孤立记录（既非主记录也非子记录）"""
    return Submission(
        id=3,
        student_id=1,
        assignment_id=1,
        version=1,
        is_latest=False,
        is_primary=False,  # 标记为非主记录
        parent_id=None,    # 但没有父记录
        relation_type=None
    )


class MockAsyncSession:
    """模拟异步会话"""

    def __init__(self):
        self.submissions = {}
        self.execute_results = []
        self.execute_call_count = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass

    def add_submission(self, submission):
        """添加测试数据"""
        self.submissions[submission.id] = submission

    async def execute(self, query):
        """模拟执行查询"""
        self.execute_call_count += 1

        # 如果有预设的执行结果，返回它
        if self.execute_results:
            result = self.execute_results.pop(0)
            if hasattr(result, '__await____'):
                return await result
            return result

        # 否则返回模拟结果
        mock_result = Mock()
        mock_result.scalar_one_or_none = Mock(return_value=None)
        mock_result.scalars.return_value.all = Mock(return_value=[])
        mock_result.rowcount = 0
        return mock_result

    async def commit(self):
        """模拟提交"""
        pass


@pytest.mark.asyncio
async def test_get_primary_when_is_primary(
    group_manager, mock_primary_submission
):
    """测试：记录本身就是主记录时返回自己"""
    mock_session = MockAsyncSession()
    mock_session.add_submission(mock_primary_submission)

    # 模拟查询返回主记录
    mock_result = Mock()
    mock_result.scalar_one_or_none = Mock(return_value=mock_primary_submission)
    mock_session.execute_results = [mock_result]

    with patch('core.deduplication.submission_group_manager.get_async_session') as mock_session_func:
        mock_session_func.return_value = lambda: mock_session

        result = await group_manager.get_primary_submission(1)

        assert result is not None
        assert result.id == 1
        assert result.is_primary is True
        assert result.parent_id is None


@pytest.mark.asyncio
async def test_get_primary_when_is_child(
    group_manager, mock_child_submission, mock_primary_submission
):
    """测试：记录是子记录时返回其父记录"""
    mock_session = MockAsyncSession()

    # 第一次调用返回子记录
    mock_result_child = Mock()
    mock_result_child.scalar_one_or_none = Mock(return_value=mock_child_submission)

    # 第二次调用返回父记录
    mock_result_parent = Mock()
    mock_result_parent.scalar_one_or_none = Mock(return_value=mock_primary_submission)

    mock_session.execute_results = [mock_result_child, mock_result_parent]

    with patch('core.deduplication.submission_group_manager.get_async_session') as mock_session_func:
        mock_session_func.return_value = lambda: mock_session

        result = await group_manager.get_primary_submission(2)

        assert result is not None
        assert result.id == 1
        assert result.is_primary is True
        assert result.parent_id is None


@pytest.mark.asyncio
async def test_get_primary_when_orphan(group_manager, mock_orphan_submission):
    """测试：记录既非主记录也非子记录时返回None"""
    mock_session = MockAsyncSession()

    # 模拟查询返回孤立记录
    mock_result = Mock()
    mock_result.scalar_one_or_none = Mock(return_value=mock_orphan_submission)
    mock_session.execute_results = [mock_result]

    with patch('core.deduplication.submission_group_manager.get_async_session') as mock_session_func:
        mock_session_func.return_value = lambda: mock_session

        result = await group_manager.get_primary_submission(3)

        # 孤立记录没有父记录且is_primary=False，应返回None
        assert result is None


@pytest.mark.asyncio
async def test_get_primary_when_not_found(group_manager):
    """测试：记录不存在时返回None"""
    mock_session = MockAsyncSession()

    # 模拟查询返回None
    mock_result = Mock()
    mock_result.scalar_one_or_none = Mock(return_value=None)
    mock_session.execute_results = [mock_result]

    with patch('core.deduplication.submission_group_manager.get_async_session') as mock_session_func:
        mock_session_func.return_value = lambda: mock_session

        result = await group_manager.get_primary_submission(999)

        assert result is None


@pytest.mark.asyncio
async def test_get_all_children(group_manager):
    """测试：获取主记录的所有子记录"""
    mock_session = MockAsyncSession()

    # 创建多个子记录
    child1 = Submission(
        id=2,
        parent_id=1,
        relation_type=RelationType.VERSION.value,
        is_primary=False
    )
    child2 = Submission(
        id=3,
        parent_id=1,
        relation_type=RelationType.VERSION.value,
        is_primary=False
    )

    mock_result = Mock()
    mock_scalars = Mock()
    mock_scalars.all = Mock(return_value=[child1, child2])
    mock_result.scalars = Mock(return_value=mock_scalars)
    mock_session.execute_results = [mock_result]

    with patch('core.deduplication.submission_group_manager.get_async_session') as mock_session_func:
        mock_session_func.return_value = lambda: mock_session

        children = await group_manager.get_all_children(1)

        assert len(children) == 2
        assert children[0].id == 2
        assert children[1].id == 3


@pytest.mark.asyncio
async def test_get_children_by_type(group_manager):
    """测试：按关系类型过滤子记录"""
    mock_session = MockAsyncSession()

    # 创建不同类型的子记录
    version_child = Submission(
        id=2,
        parent_id=1,
        relation_type=RelationType.VERSION.value,
        is_primary=False
    )

    mock_result = Mock()
    mock_scalars = Mock()
    mock_scalars.all = Mock(return_value=[version_child])
    mock_result.scalars = Mock(return_value=mock_scalars)
    mock_session.execute_results = [mock_result]

    with patch('core.deduplication.submission_group_manager.get_async_session') as mock_session_func:
        mock_session_func.return_value = lambda: mock_session

        children = await group_manager.get_all_children(
            1,
            relation_type=RelationType.VERSION.value
        )

        assert len(children) == 1
        assert children[0].relation_type == RelationType.VERSION.value


@pytest.mark.asyncio
async def test_create_relation(group_manager):
    """测试：创建父子关系"""
    mock_session = MockAsyncSession()

    # 模拟更新结果
    mock_result = Mock()
    mock_result.rowcount = 1
    mock_session.execute_results = [mock_result]

    with patch('core.deduplication.submission_group_manager.get_async_session') as mock_session_func:
        mock_session_func.return_value = lambda: mock_session

        success = await group_manager.create_relation(
            parent_id=1,
            child_id=2,
            relation_type=RelationType.VERSION.value
        )

        assert success is True
        assert mock_session.execute_call_count == 1


@pytest.mark.asyncio
async def test_create_relation_child_not_found(group_manager):
    """测试：创建关系时子记录不存在"""
    mock_session = MockAsyncSession()

    # 模拟更新结果为0行
    mock_result = Mock()
    mock_result.rowcount = 0
    mock_session.execute_results = [mock_result]

    with patch('core.deduplication.submission_group_manager.get_async_session') as mock_session_func:
        mock_session_func.return_value = lambda: mock_session

        success = await group_manager.create_relation(
            parent_id=1,
            child_id=999,
            relation_type=RelationType.VERSION.value
        )

        assert success is False


@pytest.mark.asyncio
async def test_update_primary_record(group_manager):
    """测试：更新主记录"""
    mock_session = MockAsyncSession()

    # 模拟子记录查询
    child = Submission(
        id=3,
        parent_id=1,
        is_primary=False
    )
    mock_children_result = Mock()
    mock_scalars = Mock()
    mock_scalars.all = Mock(return_value=[child])
    mock_children_result.scalars = Mock(return_value=mock_scalars)

    # 模拟更新结果
    mock_update_result = Mock()
    mock_update_result.rowcount = 1

    mock_session.execute_results = [
        mock_children_result,  # 第一次调用：获取子记录
        mock_update_result,    # 第二次调用：更新旧主记录
        mock_update_result,    # 第三次调用：更新新主记录
        mock_update_result     # 第四次调用：重新链接子记录
    ]

    with patch('core.deduplication.submission_group_manager.get_async_session') as mock_session_func:
        mock_session_func.return_value = lambda: mock_session

        success = await group_manager.update_primary_record(
            old_primary_id=1,
            new_primary_id=2
        )

        assert success is True
        assert mock_session.execute_call_count == 4  # 验证调用了4次


@pytest.mark.asyncio
async def test_get_or_create_primary_exists(group_manager, mock_primary_submission):
    """测试：获取已存在的主记录"""
    group_manager.db.get_latest_submission.return_value = mock_primary_submission

    result = await group_manager.get_or_create_primary("S001", "作业1")

    assert result is not None
    assert result.id == 1
    group_manager.db.get_latest_submission.assert_called_once_with("S001", "作业1")


@pytest.mark.asyncio
async def test_get_or_create_primary_not_exists(group_manager):
    """测试：主记录不存在时返回None"""
    group_manager.db.get_latest_submission.return_value = None

    result = await group_manager.get_or_create_primary("S001", "作业1")

    assert result is None
    group_manager.db.get_latest_submission.assert_called_once_with("S001", "作业1")
