# 去重系统重构实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 重构去重系统，建立统一服务层架构，实现强一致性事务管理和AI缓存

**Architecture:** 统一去重服务入口(DeduplicationService)协调四个专用组件(EmailDeduplicator, SubmissionDeduplicator, VersionManager, CacheManager)，使用事务性文件操作确保强一致性

**Tech Stack:** Python 3.10+, SQLAlchemy, asyncio, pathlib, pytest

---

## 文件结构概览

```
core/
├── deduplication/              # 新建目录
│   ├── __init__.py             # 公共接口导出
│   ├── service.py              # DeduplicationService 主类
│   ├── email_deduplicator.py   # EmailDeduplicator
│   ├── submission_deduplicator.py  # SubmissionDeduplicator
│   ├── version_manager.py      # VersionManager (重构)
│   ├── cache_manager.py        # CacheManager
│   └── models.py               # DeduplicationResult 等数据类
├── transactions/               # 新建目录
│   ├── __init__.py
│   ├── file_operations.py      # TransactionalFileOperation
│   └── recovery.py             # RecoveryManager
└── workflow.py                 # 修改使用新服务

database/
├── models.py                   # 添加 FileOperationsLog
├── operations.py               # 添加缓存方法
└── migrations/
    └── add_file_operations_log.py  # 新迁移脚本

tests/
├── unit/
│   ├── test_email_deduplicator.py
│   ├── test_submission_deduplicator.py
│   ├── test_version_manager.py
│   └── test_cache_manager.py
└── integration/
    ├── test_deduplication_service.py
    ├── test_transactions.py
    └── test_e2e.py

# 保留兼容层
core/deduplication.py           # 修改为委托给新服务
core/version_manager.py         # 迁移到新位置后保留兼容
```

---

## Task 1: 创建基础数据模型

**Files:**
- Create: `core/deduplication/models.py`
- Create: `tests/unit/test_deduplication_models.py`

**目标:** 定义统一的数据结构，作为整个去重系统的数据契约

- [ ] **Step 1: 创建数据模型文件**

创建 `core/deduplication/models.py`:

```python
"""去重系统数据模型"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any
from datetime import datetime
from database.models import Submission


@dataclass
class DeduplicationResult:
    """去重检查结果"""
    is_duplicate: bool                          # 是否重复
    duplicate_type: Optional[str] = None        # 'email' | 'submission' | None
    action: str = 'new'                         # 'skip' | 'update_version' | 'new'
    submission: Optional[Submission] = None     # 相关提交记录
    version: Optional[int] = None               # 版本号
    cached_data: Optional[Dict[str, Any]] = None  # 缓存的AI数据
    error: Optional[str] = None                 # 错误信息
    message: str = ""                           # 人类可读消息


@dataclass
class EmailDuplicateInfo:
    """邮件重复信息"""
    email_uid: str
    existing_submission: Submission


@dataclass
class SubmissionDuplicateInfo:
    """提交重复信息"""
    student_id: str
    assignment_name: str
    latest_version: int
    latest_submission: Submission


class DeduplicationError(Exception):
    """去重服务基础异常"""
    pass


class EmailDuplicateError(DeduplicationError):
    """邮件重复异常"""

    def __init__(self, email_uid: str, existing_submission: Submission):
        self.email_uid = email_uid
        self.existing_submission = existing_submission
        super().__init__(f"Email {email_uid} already processed")


class SubmissionDuplicateError(DeduplicationError):
    """提交重复异常"""

    def __init__(self, student_id: str, assignment_name: str, latest_version: int):
        self.student_id = student_id
        self.assignment_name = assignment_name
        self.latest_version = latest_version
        super().__init__(
            f"Submission already exists: {student_id} - {assignment_name}, "
            f"latest version: {latest_version}"
        )


class FileOperationError(DeduplicationError):
    """文件操作异常"""
    pass


class TransactionError(DeduplicationError):
    """事务异常"""
    pass
```

- [ ] **Step 2: 编写数据模型测试**

创建 `tests/unit/test_deduplication_models.py`:

```python
"""测试去重数据模型"""

import pytest
from core.deduplication.models import (
    DeduplicationResult,
    EmailDuplicateError,
    SubmissionDuplicateError,
    FileOperationError,
    TransactionError
)
from database.models import Submission


def test_deduplication_result_new_submission():
    """测试新提交结果"""
    result = DeduplicationResult(
        is_duplicate=False,
        action='new'
    )

    assert result.is_duplicate is False
    assert result.action == 'new'
    assert result.duplicate_type is None
    assert result.version is None


def test_deduplication_result_email_duplicate():
    """测试邮件重复结果"""
    mock_submission = Submission(id=1)
    result = DeduplicationResult(
        is_duplicate=True,
        duplicate_type='email',
        action='skip',
        submission=mock_submission
    )

    assert result.is_duplicate is True
    assert result.duplicate_type == 'email'
    assert result.action == 'skip'
    assert result.submission is not None


def test_deduplication_result_submission_duplicate():
    """测试提交重复结果"""
    result = DeduplicationResult(
        is_duplicate=True,
        duplicate_type='submission',
        action='update_version',
        version=2
    )

    assert result.is_duplicate is True
    assert result.duplicate_type == 'submission'
    assert result.action == 'update_version'
    assert result.version == 2


def test_email_duplicate_error():
    """测试邮件重复异常"""
    mock_submission = Submission(id=1, email_uid="test_uid")
    error = EmailDuplicateError("test_uid", mock_submission)

    assert str(error) == "Email test_uid already processed"
    assert error.email_uid == "test_uid"
    assert error.existing_submission == mock_submission


def test_submission_duplicate_error():
    """测试提交重复异常"""
    error = SubmissionDuplicateError("S001", "作业1", 2)

    assert "S001" in str(error)
    assert "作业1" in str(error)
    assert "version: 2" in str(error)
    assert error.student_id == "S001"
    assert error.assignment_name == "作业1"
    assert error.latest_version == 2


def test_file_operation_error():
    """测试文件操作异常"""
    error = FileOperationError("Failed to create folder")
    assert isinstance(error, DeduplicationError)
    assert "Failed to create folder" in str(error)


def test_transaction_error():
    """测试事务异常"""
    error = TransactionError("Transaction rolled back")
    assert isinstance(error, DeduplicationError)
    assert "Transaction rolled back" in str(error)
```

- [ ] **Step 3: 运行测试验证**

```bash
cd "D:\Programs\Python\qq邮箱作业收发"
pytest tests/unit/test_deduplication_models.py -v
```

预期: 全部通过

- [ ] **Step 4: 提交**

```bash
git add core/deduplication/models.py tests/unit/test_deduplication_models.py
git commit -m "feat(deduplication): add data models and exception classes

- Add DeduplicationResult dataclass
- Add EmailDuplicateError, SubmissionDuplicateError
- Add FileOperationError, TransactionError
- Add unit tests for all models"
```

---

## Task 2: 创建EmailDeduplicator组件

**Files:**
- Create: `core/deduplication/email_deduplicator.py`
- Create: `tests/unit/test_email_deduplicator.py`

**目标:** 实现邮件级别去重，基于email_uid判断

- [ ] **Step 1: 编写EmailDeduplicator测试**

创建 `tests/unit/test_email_deduplicator.py`:

```python
"""测试EmailDeduplicator"""

import pytest
from unittest.mock import Mock, AsyncMock
from core.deduplication.email_deduplicator import EmailDeduplicator
from database.models import Submission


@pytest.fixture
def mock_db():
    """模拟数据库操作"""
    db = Mock()
    db.get_submission_by_uid = AsyncMock()
    return db


@pytest.fixture
def email_deduplicator(mock_db):
    """创建EmailDeduplicator实例"""
    return EmailDeduplicator(mock_db)


@pytest.mark.asyncio
async def test_check_returns_true_when_email_exists(email_deduplicator, mock_db):
    """测试：邮件存在时返回True"""
    mock_submission = Submission(id=1, email_uid="existing_uid")
    mock_db.get_submission_by_uid.return_value = mock_submission

    result = await email_deduplicator.check("existing_uid")

    assert result is True
    mock_db.get_submission_by_uid.assert_called_once_with("existing_uid")


@pytest.mark.asyncio
async def test_check_returns_false_when_email_not_exists(email_deduplicator, mock_db):
    """测试：邮件不存在时返回False"""
    mock_db.get_submission_by_uid.return_value = None

    result = await email_deduplicator.check("new_uid")

    assert result is False
    mock_db.get_submission_by_uid.assert_called_once_with("new_uid")


@pytest.mark.asyncio
async def test_get_existing_returns_submission(email_deduplicator, mock_db):
    """测试：获取已存在的邮件记录"""
    mock_submission = Submission(id=1, email_uid="existing_uid")
    mock_db.get_submission_by_uid.return_value = mock_submission

    result = await email_deduplicator.get_existing("existing_uid")

    assert result == mock_submission
    assert result.id == 1


@pytest.mark.asyncio
async def test_get_existing_returns_none_when_not_found(email_deduplicator, mock_db):
    """测试：邮件不存在时返回None"""
    mock_db.get_submission_by_uid.return_value = None

    result = await email_deduplicator.get_existing("new_uid")

    assert result is None
```

- [ ] **Step 2: 运行测试验证失败**

```bash
pytest tests/unit/test_email_deduplicator.py -v
```

预期: FAIL - ModuleNotFoundError

- [ ] **Step 3: 实现EmailDeduplicator**

创建 `core/deduplication/email_deduplicator.py`:

```python
"""邮件级别去重组件"""

from typing import Optional
from database.models import Submission
from database.operations import DatabaseOperations


class EmailDeduplicator:
    """邮件级别去重 - 基于email_uid

    职责：
    - 防止同一封邮件被重复处理
    - 基于email_uid唯一约束判断
    """

    def __init__(self, db: DatabaseOperations):
        self.db = db

    async def check(self, email_uid: str) -> bool:
        """检查邮件是否已处理

        Args:
            email_uid: 邮件UID

        Returns:
            True if email exists, False otherwise
        """
        existing = await self.get_existing(email_uid)
        return existing is not None

    async def get_existing(self, email_uid: str) -> Optional[Submission]:
        """获取已存在的邮件记录

        Args:
            email_uid: 邮件UID

        Returns:
            Submission record if exists, None otherwise
        """
        return self.db.get_submission_by_uid(email_uid)
```

- [ ] **Step 4: 运行测试验证通过**

```bash
pytest tests/unit/test_email_deduplicator.py -v
```

预期: 全部通过

- [ ] **Step 5: 提交**

```bash
git add core/deduplication/email_deduplicator.py tests/unit/test_email_deduplicator.py
git commit -m "feat(deduplication): add EmailDeduplicator component

- Implement email-level deduplication based on email_uid
- Add check() method to verify if email exists
- Add get_existing() method to retrieve submission
- Add unit tests with mocked database"
```

---

## Task 3: 创建SubmissionDeduplicator组件

**Files:**
- Create: `core/deduplication/submission_deduplicator.py`
- Create: `tests/unit/test_submission_deduplicator.py`

**目标:** 实现提交级别去重，基于student_id + assignment_name判断

- [ ] **Step 1: 编写SubmissionDeduplicator测试**

创建 `tests/unit/test_submission_deduplicator.py`:

```python
"""测试SubmissionDeduplicator"""

import pytest
from unittest.mock import Mock, AsyncMock
from core.deduplication.submission_deduplicator import SubmissionDeduplicator
from database.models import Submission, Student, Assignment


@pytest.fixture
def mock_db():
    """模拟数据库操作"""
    db = Mock()
    db.get_latest_submission = AsyncMock()
    return db


@pytest.fixture
def submission_deduplicator(mock_db):
    """创建SubmissionDeduplicator实例"""
    return SubmissionDeduplicator(mock_db)


@pytest.fixture
def mock_latest_submission():
    """创建模拟的最新提交记录"""
    student = Student(id=1, student_id="S001", name="张三")
    assignment = Assignment(id=1, name="作业1")
    return Submission(
        id=1,
        student_id=1,
        assignment_id=1,
        student=student,
        assignment=assignment,
        version=1,
        is_latest=True
    )


@pytest.mark.asyncio
async def test_check_returns_true_when_submission_exists(
    submission_deduplicator, mock_db, mock_latest_submission
):
    """测试：提交存在时返回True"""
    mock_db.get_latest_submission.return_value = mock_latest_submission

    result = await submission_deduplicator.check("S001", "作业1")

    assert result is True
    mock_db.get_latest_submission.assert_called_once_with("S001", "作业1")


@pytest.mark.asyncio
async def test_check_returns_false_when_submission_not_exists(
    submission_deduplicator, mock_db
):
    """测试：提交不存在时返回False"""
    mock_db.get_latest_submission.return_value = None

    result = await submission_deduplicator.check("S001", "作业1")

    assert result is False


@pytest.mark.asyncio
async def test_get_latest_returns_submission(
    submission_deduplicator, mock_db, mock_latest_submission
):
    """测试：获取最新提交记录"""
    mock_db.get_latest_submission.return_value = mock_latest_submission

    result = await submission_deduplicator.get_latest("S001", "作业1")

    assert result == mock_latest_submission
    assert result.version == 1


@pytest.mark.asyncio
async def test_get_latest_returns_none_when_not_found(
    submission_deduplicator, mock_db
):
    """测试：提交不存在时返回None"""
    mock_db.get_latest_submission.return_value = None

    result = await submission_deduplicator.get_latest("S001", "作业1")

    assert result is None
```

- [ ] **Step 2: 运行测试验证失败**

```bash
pytest tests/unit/test_submission_deduplicator.py -v
```

预期: FAIL - ModuleNotFoundError

- [ ] **Step 3: 实现SubmissionDeduplicator**

创建 `core/deduplication/submission_deduplicator.py`:

```python
"""提交级别去重组件"""

from typing import Optional
from database.models import Submission
from database.operations import DatabaseOperations


class SubmissionDeduplicator:
    """提交级别去重 - 基于student_id + assignment_name

    职责：
    - 检测学生是否重复提交同一作业
    - 返回最新版本用于版本管理
    """

    def __init__(self, db: DatabaseOperations):
        self.db = db

    async def check(self, student_id: str, assignment_name: str) -> bool:
        """检查学生是否已提交该作业

        Args:
            student_id: 学号
            assignment_name: 作业名称

        Returns:
            True if submission exists, False otherwise
        """
        latest = await self.get_latest(student_id, assignment_name)
        return latest is not None

    async def get_latest(
        self,
        student_id: str,
        assignment_name: str
    ) -> Optional[Submission]:
        """获取最新提交记录

        Args:
            student_id: 学号
            assignment_name: 作业名称

        Returns:
            Latest Submission record if exists, None otherwise
        """
        return self.db.get_latest_submission(student_id, assignment_name)
```

- [ ] **Step 4: 运行测试验证通过**

```bash
pytest tests/unit/test_submission_deduplicator.py -v
```

预期: 全部通过

- [ ] **Step 5: 提交**

```bash
git add core/deduplication/submission_deduplicator.py tests/unit/test_submission_deduplicator.py
git commit -m "feat(deduplication): add SubmissionDeduplicator component

- Implement submission-level deduplication based on student_id + assignment_name
- Add check() method to verify if submission exists
- Add get_latest() method to retrieve latest submission
- Add unit tests with mocked database"
```

---

## Task 4: 重构VersionManager为数据库为主

**Files:**
- Create: `core/deduplication/version_manager.py`
- Create: `tests/unit/test_version_manager.py`
- Modify: `core/version_manager.py` (保留兼容性)

**目标:** 将版本管理从文件系统为主改为数据库为主

- [ ] **Step 1: 编写VersionManager测试**

创建 `tests/unit/test_version_manager.py`:

```python
"""测试VersionManager"""

import pytest
from unittest.mock import Mock, AsyncMock
from core.deduplication.version_manager import VersionManager
from database.models import Submission


@pytest.fixture
def mock_db():
    """模拟数据库操作"""
    db = Mock()
    db.get_latest_submission = AsyncMock()
    db.mark_old_versions_as_not_latest = Mock()
    return db


@pytest.fixture
def version_manager(mock_db):
    """创建VersionManager实例"""
    return VersionManager(mock_db)


@pytest.fixture
def mock_submission_v1():
    """创建版本1的模拟提交"""
    return Submission(
        id=1,
        student_id=1,
        assignment_id=1,
        version=1,
        is_latest=True
    )


@pytest.fixture
def mock_submission_v2():
    """创建版本2的模拟提交"""
    return Submission(
        id=2,
        student_id=1,
        assignment_id=1,
        version=2,
        is_latest=True
    )


@pytest.mark.asyncio
async def test_get_next_version_returns_2_when_version_1_exists(
    version_manager, mock_db, mock_submission_v1
):
    """测试：版本1存在时返回版本2"""
    mock_db.get_latest_submission.return_value = mock_submission_v1

    result = await version_manager.get_next_version("S001", "作业1")

    assert result == 2
    mock_db.get_latest_submission.assert_called_once_with("S001", "作业1")


@pytest.mark.asyncio
async def test_get_next_version_returns_1_when_no_submission_exists(
    version_manager, mock_db
):
    """测试：没有提交时返回版本1"""
    mock_db.get_latest_submission.return_value = None

    result = await version_manager.get_next_version("S001", "作业1")

    assert result == 1


@pytest.mark.asyncio
async def test_get_next_version_returns_3_when_version_2_exists(
    version_manager, mock_db, mock_submission_v2
):
    """测试：版本2存在时返回版本3"""
    mock_db.get_latest_submission.return_value = mock_submission_v2

    result = await version_manager.get_next_version("S001", "作业1")

    assert result == 3


@pytest.mark.asyncio
async def test_mark_old_versions(version_manager, mock_db):
    """测试：标记旧版本为非最新"""
    mock_db.mark_old_versions_as_not_latest.return_value = 1

    result = await version_manager.mark_old_versions("S001", "作业1", 2)

    assert result == 1
    mock_db.mark_old_versions_as_not_latest.assert_called_once_with(
        "S001", "作业1", 2
    )


@pytest.mark.asyncio
async def test_mark_old_versions_returns_0_when_no_old_versions(
    version_manager, mock_db
):
    """测试：没有旧版本时返回0"""
    mock_db.mark_old_versions_as_not_latest.return_value = 0

    result = await version_manager.mark_old_versions("S001", "作业1", 1)

    assert result == 0
```

- [ ] **Step 2: 运行测试验证失败**

```bash
pytest tests/unit/test_version_manager.py -v
```

预期: FAIL - ModuleNotFoundError

- [ ] **Step 3: 实现新VersionManager**

创建 `core/deduplication/version_manager.py`:

```python
"""版本管理组件 - 数据库为主"""

from database.operations import DatabaseOperations


class VersionManager:
    """版本管理器 - 以数据库为主

    职责：
    - 版本号分配（基于数据库查询）
    - 旧版本标记（数据库操作）
    - 不再依赖文件系统_latest文件
    """

    def __init__(self, db: DatabaseOperations):
        self.db = db

    async def get_next_version(
        self,
        student_id: str,
        assignment_name: str
    ) -> int:
        """获取下一个版本号（基于数据库）

        Args:
            student_id: 学号
            assignment_name: 作业名称

        Returns:
            下一个版本号（从1开始）
        """
        latest = self.db.get_latest_submission(student_id, assignment_name)

        if latest and latest.version:
            return latest.version + 1
        return 1

    async def mark_old_versions(
        self,
        student_id: str,
        assignment_name: str,
        current_version: int
    ) -> int:
        """标记旧版本为非最新

        Args:
            student_id: 学号
            assignment_name: 作业名称
            current_version: 当前版本号（保留为最新）

        Returns:
            被标记的旧版本数量
        """
        return self.db.mark_old_versions_as_not_latest(
            student_id, assignment_name, current_version
        )
```

- [ ] **Step 4: 运行测试验证通过**

```bash
pytest tests/unit/test_version_manager.py -v
```

预期: 全部通过

- [ ] **Step 5: 更新旧VersionManager为兼容层**

修改 `core/version_manager.py`，添加委托到新实现的兼容代码：

```python
# 在文件顶部添加导入
try:
    from core.deduplication.version_manager import VersionManager as NewVersionManager
    _use_new = True
except ImportError:
    _use_new = False

# 在VersionManager类中添加方法
if not _use_new:
    # 保留原有实现
    pass
else:
    # 委托给新实现
    def _get_new_manager(self):
        return NewVersionManager(db)

    def get_next_version_sync(self, student_id: str, name: str, assignment: str) -> int:
        """兼容方法：同步获取版本号"""
        import asyncio
        new_mgr = self._get_new_manager()
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        return loop.run_until_complete(
            new_mgr.get_next_version(student_id, assignment)
        )
```

- [ ] **Step 6: 提交**

```bash
git add core/deduplication/version_manager.py tests/unit/test_version_manager.py core/version_manager.py
git commit -m "feat(deduplication): add database-first VersionManager

- Implement VersionManager based on database queries
- Remove dependency on filesystem _latest marker files
- Add get_next_version() method using database
- Add mark_old_versions() method for database updates
- Add unit tests
- Keep old version_manager.py as compatibility layer"
```

---

## Task 5: 创建CacheManager组件

**Files:**
- Create: `core/deduplication/cache_manager.py`
- Create: `tests/unit/test_cache_manager.py`
- Modify: `database/operations.py` (添加缓存方法)

**目标:** 实现AI提取结果缓存管理

- [ ] **Step 1: 先在database/operations.py添加缓存方法**

在 `database/operations.py` 末尾添加（确保已有的缓存方法被正确实现）:

```python
# 确保这些方法存在且正确实现
def get_ai_cache(self, email_uid: str) -> Optional[Dict]:
    """已在文件中存在，验证实现正确性"""
    # 当前实现在656-681行，验证无需修改

def save_ai_cache(self, email_uid: str, result: Dict, is_fallback: bool = False):
    """已在文件中存在，验证实现正确性"""
    # 当前实现在683-721行，验证无需修改
```

- [ ] **Step 2: 编写CacheManager测试**

创建 `tests/unit/test_cache_manager.py`:

```python
"""测试CacheManager"""

import pytest
from unittest.mock import Mock
from core.deduplication.cache_manager import CacheManager


@pytest.fixture
def mock_db():
    """模拟数据库操作"""
    db = Mock()
    db.get_ai_cache = Mock()
    db.save_ai_cache = Mock()
    return db


@pytest.fixture
def cache_manager(mock_db):
    """创建CacheManager实例"""
    return CacheManager(mock_db)


def test_get_returns_cached_data(cache_manager, mock_db):
    """测试：缓存命中返回存储的数据"""
    cached_data = {
        'student_id': 'S001',
        'name': '张三',
        'assignment_name': '作业1',
        'confidence': 0.95
    }
    mock_db.get_ai_cache.return_value = cached_data

    result = cache_manager.get("test_uid")

    assert result == cached_data
    mock_db.get_ai_cache.assert_called_once_with("test_uid")


def test_get_returns_none_when_cache_miss(cache_manager, mock_db):
    """测试：缓存未命中返回None"""
    mock_db.get_ai_cache.return_value = None

    result = cache_manager.get("test_uid")

    assert result is None


def test_set_saves_to_cache(cache_manager, mock_db):
    """测试：保存数据到缓存"""
    result_data = {
        'student_id': 'S001',
        'name': '张三',
        'assignment_name': '作业1',
        'confidence': 0.95
    }

    cache_manager.set("test_uid", result_data, is_fallback=False)

    mock_db.save_ai_cache.assert_called_once_with(
        "test_uid", result_data, False
    )


def test_set_with_fallback_flag(cache_manager, mock_db):
    """测试：保存数据到缓存（标记为fallback）"""
    result_data = {
        'student_id': 'S001',
        'name': '张三',
        'assignment_name': '作业1'
    }

    cache_manager.set("test_uid", result_data, is_fallback=True)

    mock_db.save_ai_cache.assert_called_once_with(
        "test_uid", result_data, True
    )


def test_has_cache_returns_true_when_exists(cache_manager, mock_db):
    """测试：检查缓存存在时返回True"""
    mock_db.get_ai_cache.return_value = {'student_id': 'S001'}

    result = cache_manager.has("test_uid")

    assert result is True


def test_has_cache_returns_false_when_not_exists(cache_manager, mock_db):
    """测试：检查缓存不存在时返回False"""
    mock_db.get_ai_cache.return_value = None

    result = cache_manager.has("test_uid")

    assert result is False
```

- [ ] **Step 3: 运行测试验证失败**

```bash
pytest tests/unit/test_cache_manager.py -v
```

预期: FAIL - ModuleNotFoundError

- [ ] **Step 4: 实现CacheManager**

创建 `core/deduplication/cache_manager.py`:

```python
"""AI缓存管理组件"""

from typing import Optional, Dict, Any
from database.operations import DatabaseOperations


class CacheManager:
    """AI提取结果缓存管理

    职责：
    - 严格缓存模式：先检查缓存
    - 缓存未命中才调用AI
    - 保存AI结果供后续使用
    """

    def __init__(self, db: DatabaseOperations):
        self.db = db

    def get(self, email_uid: str) -> Optional[Dict[str, Any]]:
        """获取缓存的AI提取结果

        Args:
            email_uid: 邮件UID

        Returns:
            缓存的结果字典，如果不存在返回None
        """
        return self.db.get_ai_cache(email_uid)

    def set(
        self,
        email_uid: str,
        result: Dict[str, Any],
        is_fallback: bool = False
    ) -> None:
        """保存AI提取结果到缓存

        Args:
            email_uid: 邮件UID
            result: AI提取结果字典
            is_fallback: 是否为fallback结果
        """
        self.db.save_ai_cache(email_uid, result, is_fallback)

    def has(self, email_uid: str) -> bool:
        """检查是否有缓存

        Args:
            email_uid: 邮件UID

        Returns:
            True if cache exists, False otherwise
        """
        return self.get(email_uid) is not None
```

- [ ] **Step 5: 运行测试验证通过**

```bash
pytest tests/unit/test_cache_manager.py -v
```

预期: 全部通过

- [ ] **Step 6: 提交**

```bash
git add core/deduplication/cache_manager.py tests/unit/test_cache_manager.py
git commit -m "feat(deduplication): add CacheManager component

- Implement AI extraction result cache management
- Add get() method to retrieve cached data
- Add set() method to save data to cache
- Add has() method to check cache existence
- Add unit tests with mocked database
- Use strict caching strategy"
```

---

## Task 6: 创建DeduplicationService统一服务

**Files:**
- Create: `core/deduplication/service.py`
- Create: `tests/integration/test_deduplication_service.py`
- Create: `core/deduplication/__init__.py`

**目标:** 实现统一去重服务入口，协调各子组件

- [ ] **Step 1: 创建__init__.py导出公共接口**

创建 `core/deduplication/__init__.py`:

```python
"""去重系统模块

提供统一的服务接口用于去重检查和处理
"""

from core.deduplication.models import (
    DeduplicationResult,
    DeduplicationError,
    EmailDuplicateError,
    SubmissionDuplicateError,
    FileOperationError,
    TransactionError
)
from core.deduplication.service import DeduplicationService
from core.deduplication.email_deduplicator import EmailDeduplicator
from core.deduplication.submission_deduplicator import SubmissionDeduplicator
from core.deduplication.version_manager import VersionManager
from core.deduplication.cache_manager import CacheManager

__all__ = [
    'DeduplicationService',
    'DeduplicationResult',
    'EmailDeduplicator',
    'SubmissionDeduplicator',
    'VersionManager',
    'CacheManager',
    'DeduplicationError',
    'EmailDuplicateError',
    'SubmissionDuplicateError',
    'FileOperationError',
    'TransactionError',
]
```

- [ ] **Step 2: 编写DeduplicationService集成测试**

创建 `tests/integration/test_deduplication_service.py`:

```python
"""测试DeduplicationService集成"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from core.deduplication.service import DeduplicationService
from core.deduplication.models import DeduplicationResult
from database.models import Submission, Student, Assignment


@pytest.fixture
def mock_components():
    """模拟所有组件"""
    mock_db = Mock()
    mock_email_dedup = AsyncMock()
    mock_submission_dedup = AsyncMock()
    mock_version_mgr = AsyncMock()
    mock_cache_mgr = Mock()

    return {
        'db': mock_db,
        'email_dedup': mock_email_dedup,
        'submission_dedup': mock_submission_dedup,
        'version_mgr': mock_version_mgr,
        'cache_mgr': mock_cache_mgr
    }


@pytest.fixture
def service(mock_components):
    """创建DeduplicationService实例"""
    with patch('core.deduplication.service.EmailDeduplicator', return_value=mock_components['email_dedup']), \
         patch('core.deduplication.service.SubmissionDeduplicator', return_value=mock_components['submission_dedup']), \
         patch('core.deduplication.service.VersionManager', return_value=mock_components['version_mgr']), \
         patch('core.deduplication.service.CacheManager', return_value=mock_components['cache_mgr']):
        return DeduplicationService(mock_components['db'])


@pytest.mark.asyncio
async def test_check_email_duplicate(service, mock_components):
    """测试：检测到邮件重复"""
    mock_submission = Submission(id=1, email_uid="existing_uid")
    mock_components['email_dedup'].check.return_value = True
    mock_components['email_dedup'].get_existing.return_value = mock_submission

    result = await service.check_email("existing_uid")

    assert result.is_duplicate is True
    assert result.duplicate_type == 'email'
    assert result.action == 'skip'
    assert result.submission == mock_submission


@pytest.mark.asyncio
async def test_check_submission_duplicate(service, mock_components):
    """测试：检测到提交重复"""
    mock_submission = Submission(
        id=1,
        student=Student(id=1, student_id="S001", name="张三"),
        assignment=Assignment(id=1, name="作业1"),
        version=1
    )
    mock_components['email_dedup'].check.return_value = False
    mock_components['submission_dedup'].check.return_value = True
    mock_components['submission_dedup'].get_latest.return_value = mock_submission
    mock_components['version_mgr'].get_next_version.return_value = 2

    result = await service.check_submission("S001", "作业1")

    assert result.is_duplicate is True
    assert result.duplicate_type == 'submission'
    assert result.version == 2


@pytest.mark.asyncio
async def test_check_new_submission(service, mock_components):
    """测试：新提交，无重复"""
    mock_components['email_dedup'].check.return_value = False
    mock_components['submission_dedup'].check.return_value = False
    mock_components['cache_mgr'].get.return_value = None

    result = await service.check_all(
        email_uid="new_uid",
        student_id="S001",
        assignment_name="作业1"
    )

    assert result.is_duplicate is False
    assert result.action == 'new'


@pytest.mark.asyncio
async def test_check_with_cache_hit(service, mock_components):
    """测试：缓存命中"""
    cached_data = {
        'student_id': 'S001',
        'name': '张三',
        'assignment_name': '作业1'
    }
    mock_components['cache_mgr'].get.return_value = cached_data
    mock_components['email_dedup'].check.return_value = False
    mock_components['submission_dedup'].check.return_value = False

    result = await service.check_all(
        email_uid="cached_uid",
        student_id="S001",
        assignment_name="作业1"
    )

    assert result.cached_data == cached_data
```

- [ ] **Step 3: 运行测试验证失败**

```bash
pytest tests/integration/test_deduplication_service.py -v
```

预期: FAIL - ModuleNotFoundError

- [ ] **Step 4: 实现DeduplicationService**

创建 `core/deduplication/service.py`:

```python
"""统一去重服务"""

from typing import Optional, Dict, Any
from database.operations import DatabaseOperations
from core.deduplication.models import DeduplicationResult
from core.deduplication.email_deduplicator import EmailDeduplicator
from core.deduplication.submission_deduplicator import SubmissionDeduplicator
from core.deduplication.version_manager import VersionManager
from core.deduplication.cache_manager import CacheManager


class DeduplicationService:
    """统一去重服务 - 唯一入口

    职责：
    - 协调各子组件完成去重检查
    - 管理返回值标准化
    - 提供统一的检查接口
    """

    def __init__(self, db: DatabaseOperations):
        self.db = db
        self.email_deduplicator = EmailDeduplicator(db)
        self.submission_deduplicator = SubmissionDeduplicator(db)
        self.version_manager = VersionManager(db)
        self.cache_manager = CacheManager(db)

    async def check_email(self, email_uid: str) -> DeduplicationResult:
        """检查邮件是否重复

        Args:
            email_uid: 邮件UID

        Returns:
            DeduplicationResult with duplicate_type='email' if duplicate
        """
        is_duplicate = await self.email_deduplicator.check(email_uid)

        if is_duplicate:
            existing = await self.email_deduplicator.get_existing(email_uid)
            return DeduplicationResult(
                is_duplicate=True,
                duplicate_type='email',
                action='skip',
                submission=existing,
                message=f"Email {email_uid} already processed"
            )

        return DeduplicationResult(is_duplicate=False, action='new')

    async def check_submission(
        self,
        student_id: str,
        assignment_name: str
    ) -> DeduplicationResult:
        """检查提交是否重复

        Args:
            student_id: 学号
            assignment_name: 作业名称

        Returns:
            DeduplicationResult with duplicate_type='submission' if duplicate
        """
        is_duplicate = await self.submission_deduplicator.check(
            student_id, assignment_name
        )

        if is_duplicate:
            latest = await self.submission_deduplicator.get_latest(
                student_id, assignment_name
            )
            next_version = await self.version_manager.get_next_version(
                student_id, assignment_name
            )

            return DeduplicationResult(
                is_duplicate=True,
                duplicate_type='submission',
                action='update_version',
                submission=latest,
                version=next_version,
                message=f"Duplicate submission: {student_id} - {assignment_name}, "
                       f"current version: {latest.version}, next version: {next_version}"
            )

        return DeduplicationResult(is_duplicate=False, action='new')

    async def check_all(
        self,
        email_uid: str,
        student_id: str,
        assignment_name: str
    ) -> DeduplicationResult:
        """执行完整去重检查：缓存 -> 邮件 -> 提交

        Args:
            email_uid: 邮件UID
            student_id: 学号
            assignment_name: 作业名称

        Returns:
            DeduplicationResult with complete check results
        """
        # 1. 检查缓存
        cached_data = self.cache_manager.get(email_uid)

        # 2. 检查邮件重复
        email_result = await self.check_email(email_uid)
        if email_result.is_duplicate:
            email_result.cached_data = cached_data
            return email_result

        # 3. 检查提交重复
        submission_result = await self.check_submission(student_id, assignment_name)
        submission_result.cached_data = cached_data

        return submission_result
```

- [ ] **Step 5: 运行测试验证通过**

```bash
pytest tests/integration/test_deduplication_service.py -v
```

预期: 全部通过

- [ ] **Step 6: 提交**

```bash
git add core/deduplication/service.py core/deduplication/__init__.py tests/integration/test_deduplication_service.py
git commit -m "feat(deduplication): add unified DeduplicationService

- Implement unified service entry point for deduplication
- Add check_email() method for email-level deduplication
- Add check_submission() method for submission-level deduplication
- Add check_all() method for complete deduplication flow
- Coordinate all sub-components: EmailDeduplicator, SubmissionDeduplicator,
  VersionManager, CacheManager
- Add integration tests"
```

---

## Task 7: 创建事务性文件操作

**Files:**
- Create: `core/transactions/__init__.py`
- Create: `core/transactions/file_operations.py`
- Create: `core/transactions/recovery.py`
- Modify: `database/models.py` (添加FileOperationsLog模型)
- Create: `tests/integration/test_transactions.py`
- Create: `migrations/add_file_operations_log.py`

**目标:** 实现强一致性的事务管理

- [ ] **Step 1: 添加数据库模型**

在 `database/models.py` 末尾添加：

```python
class FileOperationsLog(Base):
    """文件操作事务日志 - 用于实现强一致性"""
    __tablename__ = 'file_operations_log'

    id = Column(Integer, primary_key=True)
    submission_id = Column(Integer, ForeignKey('submissions.id'), nullable=False)
    operation_type = Column(String(50), nullable=False)
    file_path = Column(String, nullable=False)
    status = Column(String(20), nullable=False, default='pending')
    created_at = Column(DateTime, default=datetime.now)
    completed_at = Column(DateTime)
    error_message = Column(String)

    submission = relationship('Submission', backref='file_operations')
```

- [ ] **Step 2: 创建迁移脚本**

创建 `migrations/add_file_operations_log.py`:

```python
"""添加文件操作日志表和索引"""

import sqlite3
from pathlib import Path
from config.settings import settings


def upgrade():
    """执行Schema升级"""
    conn = sqlite3.connect(str(settings.DATABASE_PATH))
    cursor = conn.cursor()

    try:
        # 创建文件操作日志表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS file_operations_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                submission_id INTEGER NOT NULL,
                operation_type VARCHAR(50) NOT NULL,
                file_path TEXT NOT NULL,
                status VARCHAR(20) NOT NULL DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP,
                error_message TEXT,
                FOREIGN KEY (submission_id) REFERENCES submissions(id)
            )
        """)

        # 创建复合索引
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_submissions_student_assignment_latest
            ON submissions(student_id, assignment_id, is_latest)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_submissions_student_assignment_version
            ON submissions(student_id, assignment_id, version)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_file_ops_submission
            ON file_operations_log(submission_id)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_file_ops_status
            ON file_operations_log(status)
        """)

        conn.commit()
        print("Migration completed successfully")

    except Exception as e:
        conn.rollback()
        print(f"Migration failed: {e}")
        raise
    finally:
        conn.close()


def downgrade():
    """回滚变更"""
    conn = sqlite3.connect(str(settings.DATABASE_PATH))
    cursor = conn.cursor()

    try:
        cursor.execute("DROP INDEX IF EXISTS idx_file_ops_status")
        cursor.execute("DROP INDEX IF EXISTS idx_file_ops_submission")
        cursor.execute("DROP INDEX IF EXISTS idx_submissions_student_assignment_version")
        cursor.execute("DROP INDEX IF EXISTS idx_submissions_student_assignment_latest")
        cursor.execute("DROP TABLE IF EXISTS file_operations_log")

        conn.commit()
        print("Rollback completed successfully")

    except Exception as e:
        conn.rollback()
        print(f"Rollback failed: {e}")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == 'down':
        downgrade()
    else:
        upgrade()
```

- [ ] **Step 3: 运行迁移**

```bash
cd "D:\Programs\Python\qq邮箱作业收发"
python migrations/add_file_operations_log.py
```

预期: "Migration completed successfully"

- [ ] **Step 4: 创建事务模块初始化文件**

创建 `core/transactions/__init__.py`:

```python
"""事务管理模块

提供事务性文件操作和错误恢复机制
"""

from core.transactions.file_operations import TransactionalFileOperation
from core.transactions.recovery import RecoveryManager

__all__ = [
    'TransactionalFileOperation',
    'RecoveryManager',
]
```

- [ ] **Step 5: 实现事务性文件操作**

创建 `core/transactions/file_operations.py`:

```python
"""事务性文件操作"""

import shutil
from pathlib import Path
from typing import List, Tuple
from datetime import datetime
from database.models import FileOperationsLog, db_session
from core.deduplication.models import FileOperationError


class TransactionalFileOperation:
    """事务性文件操作 - 确保与数据库一致

    所有文件操作都被记录，失败时可以回滚
    """

    def __init__(self, submission_id: int):
        self.submission_id = submission_id
        self.operations: List[Tuple[str, Path]] = []
        self.session = db_session()

    def create_folder(self, path: Path) -> bool:
        """创建文件夹（可回滚）

        Args:
            path: 文件夹路径

        Returns:
            True if successful

        Raises:
            FileOperationError: 如果创建失败
        """
        try:
            path.mkdir(parents=True, exist_ok=True)

            # 记录操作日志
            log = FileOperationsLog(
                submission_id=self.submission_id,
                operation_type='create_folder',
                file_path=str(path),
                status='completed',
                completed_at=datetime.now()
            )
            self.session.add(log)
            self.session.commit()

            # 记录用于回滚
            self.operations.append(('create_folder', path))
            return True

        except Exception as e:
            self.session.rollback()
            raise FileOperationError(f"Failed to create folder {path}: {e}")

    def save_file(self, path: Path, content: bytes) -> bool:
        """保存文件（可回滚）

        Args:
            path: 文件路径
            content: 文件内容

        Returns:
            True if successful

        Raises:
            FileOperationError: 如果保存失败
        """
        try:
            # 确保父目录存在
            path.parent.mkdir(parents=True, exist_ok=True)

            with open(path, 'wb') as f:
                f.write(content)

            # 记录操作日志
            log = FileOperationsLog(
                submission_id=self.submission_id,
                operation_type='save_file',
                file_path=str(path),
                status='completed',
                completed_at=datetime.now()
            )
            self.session.add(log)
            self.session.commit()

            # 记录用于回滚
            self.operations.append(('save_file', path))
            return True

        except Exception as e:
            self.session.rollback()
            # 清理已创建的文件
            self._rollback()
            raise FileOperationError(f"Failed to save file {path}: {e}")

    def delete_file(self, path: Path) -> bool:
        """删除文件

        Args:
            path: 文件路径

        Returns:
            True if successful
        """
        try:
            if path.exists():
                path.unlink()

            log = FileOperationsLog(
                submission_id=self.submission_id,
                operation_type='delete_file',
                file_path=str(path),
                status='completed',
                completed_at=datetime.now()
            )
            self.session.add(log)
            self.session.commit()

            return True

        except Exception as e:
            self.session.rollback()
            raise FileOperationError(f"Failed to delete file {path}: {e}")

    def _rollback(self):
        """回滚所有文件操作"""
        for op_type, path in reversed(self.operations):
            try:
                if op_type == 'save_file' and path.exists():
                    path.unlink()
                elif op_type == 'create_folder' and path.exists():
                    shutil.rmtree(path)
            except Exception as e:
                print(f"Warning: Failed to rollback {path}: {e}")

    def cleanup(self):
        """清理资源"""
        self.session.close()
```

- [ ] **Step 6: 实现恢复管理器**

创建 `core/transactions/recovery.py`:

```python
"""错误恢复管理器"""

from typing import Optional
from database.models import FileOperationsLog, db_session


class RecoveryManager:
    """错误恢复管理器

    处理未完成的文件操作，恢复系统到一致状态
    """

    def __init__(self):
        self.session = db_session()

    def recover_incomplete_operations(self) -> dict:
        """恢复未完成的文件操作

        Returns:
            恢复结果统计: {'total': int, 'recovered': int, 'failed': int}
        """
        pending = self.session.query(FileOperationsLog).filter_by(
            status='pending'
        ).all()

        results = {'total': len(pending), 'recovered': 0, 'failed': 0}

        for log in pending:
            try:
                if self._retry_operation(log):
                    results['recovered'] += 1
                else:
                    results['failed'] += 1
            except Exception as e:
                print(f"Failed to recover operation {log.id}: {e}")
                results['failed'] += 1

        return results

    def _retry_operation(self, log: FileOperationsLog) -> bool:
        """重试失败的操作

        Args:
            log: 操作日志记录

        Returns:
            True if successful
        """
        from pathlib import Path

        if log.operation_type == 'save_file':
            path = Path(log.file_path)
            if path.exists():
                log.status = 'completed'
                log.completed_at = Optional[datetime]
                self.session.commit()
                return True
            else:
                log.error_message = f"File not found: {log.file_path}"
                self.session.commit()
                return False

        return False

    def cleanup_old_logs(self, days: int = 7):
        """清理旧的已完成日志

        Args:
            days: 保留天数
        """
        from datetime import timedelta
        cutoff = datetime.now() - timedelta(days=days)

        old_logs = self.session.query(FileOperationsLog).filter(
            FileOperationsLog.status == 'completed',
            FileOperationsLog.completed_at < cutoff
        ).all()

        count = len(old_logs)
        for log in old_logs:
            self.session.delete(log)

        self.session.commit()
        return count
```

- [ ] **Step 7: 编写事务测试**

创建 `tests/integration/test_transactions.py`:

```python
"""测试事务性文件操作"""

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


def test_create_folder_success(temp_dir):
    """测试：成功创建文件夹"""
    file_op = TransactionalFileOperation(submission_id=1)
    test_path = temp_dir / "test_folder"

    result = file_op.create_folder(test_path)

    assert result is True
    assert test_path.exists()
    assert ('create_folder', test_path) in file_op.operations
    file_op.cleanup()


def test_create_folder_records_log(temp_dir):
    """测试：创建文件夹记录日志"""
    file_op = TransactionalFileOperation(submission_id=1)
    test_path = temp_dir / "test_folder"

    file_op.create_folder(test_path)

    logs = file_op.session.query(FileOperationsLog).filter_by(
        submission_id=1,
        operation_type='create_folder'
    ).all()

    assert len(logs) == 1
    assert logs[0].status == 'completed'
    file_op.cleanup()


def test_save_file_success(temp_dir):
    """测试：成功保存文件"""
    file_op = TransactionalFileOperation(submission_id=1)
    test_path = temp_dir / "test_file.txt"
    content = b"test content"

    result = file_op.save_file(test_path, content)

    assert result is True
    assert test_path.exists()
    assert test_path.read_bytes() == content
    file_op.cleanup()


def test_save_file_creates_parent_dir(temp_dir):
    """测试：保存文件时自动创建父目录"""
    file_op = TransactionalFileOperation(submission_id=1)
    test_path = temp_dir / "subdir" / "test_file.txt"
    content = b"test content"

    result = file_op.save_file(test_path, content)

    assert result is True
    assert test_path.exists()
    assert test_path.parent.exists()
    file_op.cleanup()


def test_rollback_on_failure(temp_dir):
    """测试：失败时回滚已创建的文件"""
    file_op = TransactionalFileOperation(submission_id=1)

    # 创建第一个文件
    file1 = temp_dir / "file1.txt"
    file_op.save_file(file1, b"content1")

    # 创建第二个文件（模拟失败）
    file2 = temp_dir / "file2.txt"
    with pytest.raises(FileOperationError):
        file_op.save_file(file2, None)  # 这会失败

    # 验证回滚：第一个文件应该被删除
    assert not file1.exists()
    assert not file2.exists()
```

- [ ] **Step 8: 运行测试**

```bash
pytest tests/integration/test_transactions.py -v
```

预期: 全部通过

- [ ] **Step 9: 提交**

```bash
git add core/transactions/ database/models.py migrations/add_file_operations_log.py tests/integration/test_transactions.py
git commit -m "feat(transactions): add transactional file operations

- Add FileOperationsLog model for tracking file operations
- Create migration script for new table and indexes
- Implement TransactionalFileOperation with rollback support
- Implement RecoveryManager for incomplete operations
- Add integration tests
- Ensure strong consistency between DB and filesystem"
```

---

## Task 8: 更新AI提取器使用缓存

**Files:**
- Modify: `ai/extractor.py`
- Create: `tests/unit/test_ai_extractor_cache.py`

**目标:** AI提取优先使用缓存

- [ ] **Step 1: 查看当前AI提取器实现**

```bash
cat "D:\Programs\Python\qq邮箱作业收发\ai\extractor.py"
```

- [ ] **Step 2: 修改AI提取器添加缓存检查**

在 `ai/extractor.py` 中添加缓存逻辑：

```python
# 在类中添加缓存管理器
from database.operations import db

class AIExtractor:
    def __init__(self):
        # ... 现有初始化代码 ...
        self.cache_manager = db  # 用于缓存访问

    async def extract_student_info(
        self,
        subject: str,
        sender: str,
        attachments: list
    ) -> dict:
        """提取学生信息（带缓存）"""

        # 构建缓存键（使用subject或附件hash）
        cache_key = self._build_cache_key(subject, sender, attachments)

        # 1. 先检查缓存
        cached = self.cache_manager.get_ai_cache(cache_key)
        if cached:
            print(f"AI cache hit for {cache_key}")
            return cached

        # 2. 缓存未命中，调用AI
        print(f"AI cache miss, calling API for {cache_key}")
        result = await self._call_ai_api(subject, sender, attachments)

        # 3. 保存到缓存
        self.cache_manager.save_ai_cache(cache_key, result, is_fallback=False)

        return result

    def _build_cache_key(self, subject: str, sender: str, attachments: list) -> str:
        """构建缓存键"""
        import hashlib
        key_data = f"{subject}:{sender}"
        if attachments:
            # 使用第一个附件的文件名作为缓存键的一部分
            key_data += f":{attachments[0].get('filename', '')}"
        return hashlib.md5(key_data.encode()).hexdigest()
```

- [ ] **Step 3: 提交**

```bash
git add ai/extractor.py
git commit -m "feat(ai): add cache support to AI extractor

- Check cache before calling AI API
- Save results to cache after extraction
- Use MD5 hash as cache key
- Reduce API calls for identical emails"
```

---

## Task 9: 更新Workflow使用新服务

**Files:**
- Modify: `core/workflow.py`
- Create: `tests/integration/test_e2e.py`

**目标:** 更新工作流使用新的去重服务

- [ ] **Step 1: 修改workflow.py导入新服务**

在 `core/workflow.py` 顶部添加导入：

```python
# 添加新导入
from core.deduplication.service import DeduplicationService
from core.transactions.file_operations import TransactionalFileOperation
```

- [ ] **Step 2: 修改AssignmentWorkflow初始化**

在 `AssignmentWorkflow.__init__` 中添加：

```python
def __init__(self):
    # ... 现有代码 ...
    self.dedup_service = DeduplicationService(db)
```

- [ ] **Step 3: 修改_process_extracted_info使用新服务**

替换原有的去重检查逻辑：

```python
async def _process_extracted_info(self, email_uid: str, email_data: Dict,
                                  student_info: Dict, is_retry: bool = False) -> dict:
    """处理已提取的信息"""
    # ... 现有代码 ...

    # 使用新服务进行去重检查
    dedup_result = await self.dedup_service.check_all(
        email_uid=email_uid,
        student_id=student_id,
        assignment_name=assignment_name
    )

    if dedup_result.is_duplicate:
        if dedup_result.duplicate_type == 'email':
            print(f"Email already processed: {email_uid}")
            return {'success': True, 'action': 'skip', 'reason': 'email_duplicate'}

        elif dedup_result.duplicate_type == 'submission':
            print(f"Duplicate submission: {student_id} - {assignment_name}")
            # 使用事务性文件操作创建新版本
            return await self._handle_duplicate_version(
                email_uid, email_data, student_info, dedup_result.version
            )

    # ... 继续正常处理 ...
```

- [ ] **Step 4: 添加版本更新处理方法**

```python
async def _handle_duplicate_version(
    self,
    email_uid: str,
    email_data: Dict,
    student_info: Dict,
    new_version: int
) -> dict:
    """处理重复提交，创建新版本"""
    from core.transactions.file_operations import TransactionalFileOperation

    student_id = student_info['student_id']
    student_name = student_info['name']
    assignment_name = student_info['assignment_name']

    try:
        # 1. 创建新的提交记录
        submission = self.db.create_submission(
            student_id=student_id,
            assignment_name=assignment_name,
            email_uid=email_uid,
            email_subject=email_data['subject'],
            sender_email=email_data['sender_email'],
            sender_name=student_name,
            submission_time=datetime.now(),
            version=new_version,
            is_latest=True
        )

        # 2. 使用事务性文件操作保存附件
        file_op = TransactionalFileOperation(submission.id)
        try:
            local_path = self.storage.store_submission(
                assignment_name=assignment_name,
                student_id=student_id,
                name=student_name,
                attachments=email_data['attachments'],
                version=new_version
            )

            # 3. 标记旧版本
            await self.dedup_service.version_manager.mark_old_versions(
                student_id, assignment_name, new_version
            )

            # 4. 移动邮件
            self.parser.move_to_folder(email_uid, self.settings.TARGET_FOLDER)

            # 5. 发送更新通知
            if self.settings.ENABLE_REPLY:
                self.smtp.send_reply(
                    to_email=email_data['sender_email'],
                    student_name=student_name,
                    assignment_name=assignment_name,
                    custom_message="你的作业已更新为最新版本。"
                )

            file_op.cleanup()
            return {'success': True, 'action': 'updated_duplicate', 'version': new_version}

        except Exception as e:
            file_op._rollback()
            raise e

    except Exception as e:
        print(f"Error handling duplicate: {e}")
        return {'success': False, 'error': str(e), 'action': 'duplicate_failed'}
```

- [ ] **Step 5: 更新旧deduplication.py为兼容层**

修改 `core/deduplication.py`，委托给新服务：

```python
"""旧版去重处理 - 兼容层

此模块保留以向后兼容，实际逻辑已迁移到 DeduplicationService
"""

from core.deduplication.service import DeduplicationService
from core.deduplication.models import DeduplicationResult
from database.operations import db

class DeduplicationHandler:
    """兼容层：委托给新服务"""

    def __init__(self):
        self._service = DeduplicationService(db)

    async def is_duplicate(self, student_id: str, student_name: str,
                          assignment_name: str) -> bool:
        """兼容旧接口"""
        result = await self._service.check_submission(student_id, assignment_name)
        return result.is_duplicate

    async def handle_duplicate(self, new_email_uid: str, student_id: str,
                              student_name: str, assignment_name: str,
                              sender_email: str, attachments: list) -> dict:
        """兼容旧接口 - 返回新版本信息"""
        result = await self._service.check_submission(student_id, assignment_name)
        return {
            'success': True,
            'version': result.version,
            'message': result.message
        }

    async def check_and_handle_duplicate(self, student_id: str, student_name: str,
                                        assignment_name: str, email_uid: str,
                                        sender_email: str, email_subject: str,
                                        attachments: list) -> tuple:
        """兼容旧接口"""
        result = await self._service.check_all(email_uid, student_id, assignment_name)
        return result.is_duplicate, {'success': True, 'result': result}

# 保持全局实例兼容
deduplication_handler = DeduplicationHandler()
```

- [ ] **Step 6: 编写E2E测试**

创建 `tests/integration/test_e2e.py`:

```python
"""端到端测试"""

import pytest
from core.workflow import AssignmentWorkflow
from database.operations import db


@pytest.mark.asyncio
async def test_new_submission_flow():
    """测试：新提交流程"""
    workflow = AssignmentWorkflow()

    # Mock邮件数据
    # ... 模拟完整流程 ...

    result = await workflow.process_new_email("test_uid")

    assert result['success'] is True
    assert result['action'] == 'processed'


@pytest.mark.asyncio
async def test_duplicate_submission_creates_version():
    """测试：重复提交创建新版本"""
    workflow = AssignmentWorkflow()

    # 第一次提交
    await workflow.process_new_email("email1_uid")

    # 第二次提交（相同学生和作业）
    result = await workflow.process_new_email("email2_uid")

    assert result['success'] is True
    assert result['action'] == 'updated_duplicate'
```

- [ ] **Step 7: 运行E2E测试**

```bash
pytest tests/integration/test_e2e.py -v
```

- [ ] **Step 8: 提交**

```bash
git add core/workflow.py core/deduplication.py tests/integration/test_e2e.py
git commit -m "refactor(workflow): integrate new deduplication service

- Update AssignmentWorkflow to use DeduplicationService
- Add _handle_duplicate_version method with transactional file operations
- Update old deduplication.py as compatibility layer
- Add E2E tests for complete workflow
- Maintain backward compatibility"
```

---

## Task 10: 运行完整测试套件

**目标:** 确保所有测试通过

- [ ] **Step 1: 运行所有单元测试**

```bash
pytest tests/unit/ -v --tb=short
```

预期: 全部通过

- [ ] **Step 2: 运行所有集成测试**

```bash
pytest tests/integration/ -v --tb=short
```

预期: 全部通过

- [ ] **Step 3: 运行完整测试套件**

```bash
pytest tests/ -v --cov=core/deduplication --cov=core/transactions
```

预期: 全部通过，覆盖率 > 80%

- [ ] **Step 4: 手动测试**

使用实际邮箱测试完整流程：
1. 发送新作业邮件
2. 发送重复邮件（同一学生同一作业）
3. 验证版本创建
4. 验证邮件回复

- [ ] **Step 5: 提交最终代码**

```bash
git add tests/
git commit -m "test(deduplication): add comprehensive test coverage

- All unit tests passing
- All integration tests passing
- E2E tests covering main scenarios
- Code coverage > 80%"
```

---

## Task 11: 更新文档

**Files:**
- Create: `docs/deduplication.md`
- Modify: `CHANGELOG.md`
- Modify: `README.md` (可选)

- [ ] **Step 1: 创建去重系统文档**

创建 `docs/deduplication.md`:

```markdown
# 去重系统文档

## 概述

去重系统提供统一的邮件和提交去重服务，确保数据一致性。

## 架构

```
DeduplicationService
├── EmailDeduplicator (邮件级别)
├── SubmissionDeduplicator (提交级别)
├── VersionManager (版本管理)
└── CacheManager (AI缓存)
```

## 使用方法

### 基本使用

\`\`\`python
from core.deduplication import DeduplicationService

service = DeduplicationService(db)
result = await service.check_all(email_uid, student_id, assignment_name)

if result.is_duplicate:
    print(f"Duplicate: {result.duplicate_type}")
\`\`\`

### 事务性文件操作

\`\`\`python
from core.transactions import TransactionalFileOperation

file_op = TransactionalFileOperation(submission_id)
try:
    file_op.create_folder(path)
    file_op.save_file(file_path, content)
except FileOperationError:
    file_op._rollback()
\`\`\`

## API 参考

详见 `docs/superpowers/specs/2026-04-24-deduplication-redesign-design.md`
```

- [ ] **Step 2: 更新CHANGELOG**

在 `CHANGELOG.md` 添加：

```markdown
## [Unreleased]

### Added
- 统一去重服务层 (DeduplicationService)
- 事务性文件操作支持
- AI提取结果缓存
- 新的数据库索引优化查询性能
- 文件操作日志表 (file_operations_log)

### Changed
- 重构版本管理为数据库为主
- 改进错误处理和异常分类
- 优化去重检查流程

### Fixed
- 修复文件操作与数据库不一致问题
- 修复重复邮件处理问题
```

- [ ] **Step 3: 提交文档**

```bash
git add docs/
git commit -m "docs: add deduplication system documentation

- Add comprehensive deduplication system docs
- Update CHANGELOG with new features
- Add usage examples and API reference"
```

---

## Task 12: 最终验证

**目标:** 确保系统完全可用

- [ ] **Step 1: 运行迁移脚本验证**

```bash
python migrations/add_file_operations_log.py
```

预期: 已存在的表跳过，无错误

- [ ] **Step 2: 验证数据库Schema**

```bash
sqlite3 "D:\Programs\Python\qq邮箱作业收发\submissions.db" ".schema file_operations_log"
```

预期: 显示完整的表结构

- [ ] **Step 3: 验证索引创建**

```bash
sqlite3 submissions.db ".indexes"
```

预期: 包含新创建的索引

- [ ] **Step 4: 运行完整测试**

```bash
pytest tests/ -v --cov
```

预期: 全部通过

- [ ] **Step 5: 创建最终标签**

```bash
git tag -a v2.0.0-deduplication-refactor -m "Complete deduplication system refactor"
git push origin v2.0.0-deduplication-refactor
```

---

## 完成检查清单

在实施完成后，验证以下内容：

- [ ] 所有单元测试通过
- [ ] 所有集成测试通过
- [ ] E2E测试覆盖主要场景
- [ ] 数据库迁移成功执行
- [ ] 文档完整准确
- [ ] 代码审查完成
- [ ] 性能测试显示无回退
- [ ] 手动测试验证
- [ ] 向后兼容性验证
- [ ] CHANGELOG更新

---

**计划版本**: 1.0
**创建日期**: 2026-04-24
**预计时间**: 8-12天
