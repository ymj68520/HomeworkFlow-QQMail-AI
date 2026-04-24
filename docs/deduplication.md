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

```python
from core.deduplication import DeduplicationService
from database.async_operations import async_db

service = DeduplicationService(async_db)
result = await service.check_all(email_uid, student_id, assignment_name)

if result.is_duplicate:
    print(f"Duplicate: {result.duplicate_type}")
    if result.duplicate_type == 'submission':
        print(f"Next version: {result.version}")
```

### 异步使用

所有去重服务方法都是异步的，需要使用 `await`：

```python
# 检查邮件重复
result = await service.check_email("email_uid")

# 检查提交重复
result = await service.check_submission("S001", "作业1")

# 完整检查（包括缓存）
result = await service.check_all("email_uid", "S001", "作业1")
```

### 事务性文件操作

```python
from core.transactions import TransactionalFileOperation

file_op = TransactionalFileOperation(submission_id)
try:
    await file_op.create_folder(path)
    await file_op.save_file(file_path, content)
except FileOperationError:
    await file_op._rollback()
finally:
    await file_op.cleanup()
```

## 返回值

### DeduplicationResult

```python
@dataclass
class DeduplicationResult:
    is_duplicate: bool              # 是否重复
    duplicate_type: Optional[str]    # 'email' | 'submission' | None
    action: str                      # 'skip' | 'update_version' | 'new'
    submission: Optional[Submission] # 相关提交记录
    version: Optional[int]           # 版本号
    cached_data: Optional[Dict]      # 缓存的AI数据
    error: Optional[str]             # 错误信息
    message: str                     # 人类可读消息
```

## API 参考

详见 `docs/superpowers/specs/2026-04-24-deduplication-redesign-design.md`

## 数据库Schema

### 新增表

- `file_operations_log`: 文件操作事务日志
- `ai_extraction_cache`: AI提取结果缓存（已存在）

### 新增索引

- `idx_submissions_student_assignment_latest`: 优化最新版本查询
- `idx_submissions_student_assignment_version`: 优化版本查询
- `idx_file_ops_submission`: 文件操作日志查询
- `idx_file_ops_status`: 文件操作状态查询

## 迁移

运行数据库迁移：

```bash
python migrations/add_file_operations_log.py
```

## 错误处理

### 异常类

- `DeduplicationError`: 基础异常
- `EmailDuplicateError`: 邮件重复异常
- `SubmissionDuplicateError`: 提交重复异常
- `FileOperationError`: 文件操作异常
- `TransactionError`: 事务异常

### 错误恢复

使用 `RecoveryManager` 恢复失败的操作：

```python
from core.transactions import RecoveryManager

recovery_mgr = RecoveryManager()
results = await recovery_mgr.recover_incomplete_operations()
print(f"Recovered: {results['recovered']}/{results['total']}")
```
