# 去重系统重构设计文档

**日期**: 2026-04-24
**作者**: Claude
**状态**: 设计阶段

---

## 1. 概述

### 1.1 背景

当前QQ邮箱作业收发系统的去重逻辑存在以下问题：

- **职责重叠**: `database/operations.py` 和 `core/deduplication.py` 都有重复检查逻辑
- **操作重复**: 邮件移动操作在多处实现，不一致
- **版本管理分散**: 文件系统和数据库都需要维护版本信息，容易不同步
- **AI缓存未充分利用**: `ai_extraction_cache` 表存在但未被使用
- **错误处理不一致**: 不同组件返回不同格式的错误信息
- **缺乏事务管理**: 文件操作和数据库操作分离，可能导致数据不一致

### 1.2 重构目标

1. **简化架构**: 建立清晰的分层架构，消除职责重叠
2. **提高可靠性**: 增强事务管理、错误恢复、并发控制
3. **提升性能**: 充分利用缓存机制，减少重复AI调用

### 1.3 设计原则

- **强一致性**: 文件操作失败则回滚数据库
- **数据库为主**: 版本管理以数据库为准
- **严格缓存**: AI提取优先使用缓存
- **职责清晰**: 每个组件专注单一职责
- **向后兼容**: 保留旧接口，平滑迁移

---

## 2. 整体架构

### 2.1 架构层次

```
┌─────────────────────────────────────────────────────────┐
│                    AssignmentWorkflow                    │
│                    (业务流程协调层)                        │
└──────────────────────────┬──────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│                  DeduplicationService                    │
│                  (统一去重服务层)                          │
│  ┌──────────────────────────────────────────────────┐  │
│  │           check_and_process()                    │  │
│  │              (统一入口，事务管理)                  │  │
│  └──────────────────────────────────────────────────┘  │
└──────────────────────────┬──────────────────────────────┘
                           │
        ┌──────────────────┼──────────────────┐
        ▼                  ▼                  ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│ Email        │  │ Submission   │  │ Version      │
│ Deduplicator │  │ Deduplicator │  │ Manager      │
└──────────────┘  └──────────────┘  └──────────────┘
        │                  │                  │
        ▼                  ▼                  ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│ Cache        │  │ Database     │  │ File System  │
│ Manager      │  │ Operations   │  │ Storage      │
└──────────────┘  └──────────────┘  └──────────────┘
```

### 2.2 职责划分

| 层级 | 组件 | 职责 |
|------|------|------|
| 业务流程 | `AssignmentWorkflow` | 协调整个邮件处理流程 |
| 去重服务 | `DeduplicationService` | 统一去重入口，事务管理 |
| 邮件去重 | `EmailDeduplicator` | email_uid级别去重 |
| 提交去重 | `SubmissionDeduplicator` | student+assignment级别去重 |
| 版本管理 | `VersionManager` | 版本号管理，旧版本标记 |
| 缓存管理 | `CacheManager` | AI提取结果缓存管理 |

---

## 3. 数据流设计

### 3.1 邮件处理流程

```
接收邮件 → 解析邮件 → AI提取 → 去重检查 → 处理分支
                                   │
                    ┌──────────────┼──────────────┐
                    ▼              ▼              ▼
            邮件重复          提交重复          新提交
            (跳过处理)        (创建新版本)      (正常处理)
```

### 3.2 去重检查步骤

1. **检查AI缓存**: 优先从缓存获取AI提取结果
2. **检查邮件重复**: 基于 `email_uid` 判断邮件是否已处理
3. **检查提交重复**: 基于 `student_id + assignment_name` 判断是否重复提交

### 3.3 事务边界

```
开始数据库事务
    │
    ├─ 数据库操作1
    ├─ 数据库操作2
    ├─ 数据库操作3
    │
    ├─ 文件系统操作 (在事务内)
    │   ├─ 创建版本文件夹
    │   ├─ 保存附件
    │   └─ 失败则抛出异常
    │
    ├─ 全部成功 → Commit
    └─ 任何失败 → Rollback + 清理文件
```

---

## 4. 组件详细设计

### 4.1 DeduplicationService

统一去重服务入口，协调各子组件，管理事务边界。

```python
class DeduplicationService:
    """统一去重服务"""

    async def check_and_process(
        self,
        email_uid: str,
        student_id: str,
        student_name: str,
        assignment_name: str,
        sender_email: str,
        attachments: list
    ) -> DeduplicationResult:
        """
        统一去重检查和处理

        步骤：
        1. 检查AI缓存
        2. 检查邮件重复
        3. 检查提交重复
        4. 根据结果执行处理
        5. 事务管理确保一致性
        """
```

### 4.2 EmailDeduplicator

邮件级别去重，防止同一封邮件被重复处理。

```python
class EmailDeduplicator:
    """邮件级别去重 - 基于email_uid"""

    async def check(self, email_uid: str) -> bool:
        """检查邮件是否已处理"""

    async def get_existing(self, email_uid: str) -> Optional[Submission]:
        """获取已存在的邮件记录"""
```

### 4.3 SubmissionDeduplicator

提交级别去重，检测学生是否重复提交同一作业。

```python
class SubmissionDeduplicator:
    """提交级别去重 - 基于student_id + assignment_name"""

    async def check(self, student_id: str, assignment_name: str) -> bool:
        """检查学生是否已提交该作业"""

    async def get_latest(self, student_id: str, assignment_name: str) -> Optional[Submission]:
        """获取最新提交记录"""
```

### 4.4 VersionManager

版本管理器，以数据库为主进行版本控制。

```python
class VersionManager:
    """版本管理器 - 数据库为主"""

    async def get_next_version(self, student_id: str, assignment_name: str) -> int:
        """获取下一个版本号（基于数据库）"""

    async def mark_old_versions(
        self,
        student_id: str,
        assignment_name: str,
        current_version: int
    ) -> int:
        """标记旧版本为非最新"""
```

### 4.5 CacheManager

AI缓存管理，严格缓存模式。

```python
class CacheManager:
    """AI提取结果缓存管理"""

    async def get(self, email_uid: str) -> Optional[Dict]:
        """获取缓存的AI提取结果"""

    async def set(self, email_uid: str, result: Dict, is_fallback: bool = False) -> None:
        """保存AI提取结果到缓存"""
```

### 4.6 统一返回值

```python
@dataclass
class DeduplicationResult:
    """统一返回值"""
    is_duplicate: bool              # 是否重复
    duplicate_type: Optional[str]   # 重复类型: 'email' | 'submission' | None
    action: str                     # 执行的操作: 'skip' | 'update_version' | 'new'
    submission: Optional[Submission] # 相关提交记录
    version: Optional[int]          # 版本号
    cached_data: Optional[Dict]     # 缓存的AI数据
    error: Optional[str]            # 错误信息
```

---

## 5. 数据库Schema变更

### 5.1 新增表：file_operations_log

用于实现强一致性的文件操作事务日志。

```sql
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
);
```

### 5.2 新增索引

```sql
-- 优化 student + assignment + latest 查询
CREATE INDEX IF NOT EXISTS idx_submissions_student_assignment_latest
ON submissions(student_id, assignment_id, is_latest);

-- 优化版本查询
CREATE INDEX IF NOT EXISTS idx_submissions_student_assignment_version
ON submissions(student_id, assignment_id, version);

-- AI缓存索引
CREATE INDEX IF NOT EXISTS idx_ai_cache_email_uid
ON ai_extraction_cache(email_uid);
```

### 5.3 数据模型

```python
class FileOperationsLog(Base):
    """文件操作事务日志"""
    __tablename__ = 'file_operations_log'

    id = Column(Integer, primary_key=True)
    submission_id = Column(Integer, ForeignKey('submissions.id'), nullable=False)
    operation_type = Column(String(50), nullable=False)
    file_path = Column(String, nullable=False)
    status = Column(String(20), nullable=False, default='pending')
    created_at = Column(DateTime, default=datetime.now)
    completed_at = Column(DateTime)
    error_message = Column(String)
```

---

## 6. 错误处理与恢复

### 6.1 错误分类

| 类型 | 示例 | 处理策略 |
|------|------|----------|
| 可恢复错误 | 网络临时故障 | 重试 |
| 事务回滚错误 | 文件创建失败 | 回滚+日志 |
| 致命错误 | 数据库连接丢失 | 中止+告警 |

### 6.2 事务性文件操作

```python
class TransactionalFileOperation:
    """事务性文件操作"""

    async def create_folder(self, path: Path) -> bool:
        """创建文件夹（可回滚）"""

    async def save_file(self, path: Path, content: bytes) -> bool:
        """保存文件（可回滚）"""

    async def _rollback(self):
        """回滚所有文件操作"""
```

### 6.3 异常类

```python
class DeduplicationError(Exception):
    """去重服务基础异常"""

class EmailDuplicateError(DeduplicationError):
    """邮件重复异常"""

class SubmissionDuplicateError(DeduplicationError):
    """提交重复异常"""

class FileOperationError(DeduplicationError):
    """文件操作异常"""

class TransactionError(DeduplicationError):
    """事务异常"""
```

---

## 7. 测试策略

### 7.1 测试金字塔

- **单元测试 (60%)**: 每个组件独立测试
- **集成测试 (30%)**: 服务集成测试
- **E2E测试 (10%)**: 端到端流程测试

### 7.2 关键测试场景

1. 新提交流程
2. 重复提交创建新版本
3. 邮件重复跳过处理
4. 文件操作失败时数据库回滚
5. 部分失败时清理已创建文件
6. 缓存命中/未命中

---

## 8. 实施计划

### 8.1 阶段划分

| 阶段 | 时长 | 内容 |
|------|------|------|
| 1. 基础重构 | 2-3天 | 创建新组件，单元测试 |
| 2. 事务管理 | 2-3天 | 实现事务性操作，集成测试 |
| 3. AI缓存 | 1-2天 | 实现缓存逻辑，性能测试 |
| 4. 集成测试 | 2-3天 | 更新Workflow，E2E测试 |
| 5. 文档部署 | 1天 | 更新文档，数据迁移 |

### 8.2 文件结构

```
core/
├── deduplication/
│   ├── __init__.py
│   ├── service.py
│   ├── email_deduplicator.py
│   ├── submission_deduplicator.py
│   ├── version_manager.py
│   ├── cache_manager.py
│   └── models.py
├── transactions/
│   ├── __init__.py
│   ├── file_operations.py
│   └── recovery.py

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
```

### 8.3 向后兼容

保留 `DeduplicationHandler` 旧接口，委托给新服务实现，确保平滑迁移。

---

## 9. 风险与缓解

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| 数据迁移失败 | 高 | 先在测试环境验证，保留备份 |
| 性能下降 | 中 | 添加性能测试，优化查询 |
| 现有功能破坏 | 高 | 保留兼容层，充分测试 |
| 事务回滚失败 | 中 | 添加告警，人工介入 |

---

## 10. 验收标准

1. ✅ 所有单元测试通过
2. ✅ 所有集成测试通过
3. ✅ E2E测试覆盖主要场景
4. ✅ 性能测试显示无回退
5. ✅ 代码审查通过
6. ✅ 文档完整
7. ✅ 数据迁移脚本验证通过

---

**文档版本**: 1.0
**最后更新**: 2026-04-24
