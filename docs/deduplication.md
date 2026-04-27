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

## 新功能：模糊匹配

### 概述

模糊匹配功能用于检测可能的重复提交，处理以下场景：
- 学号相同但姓名不同（可能是姓名错误）
- 姓名相同但学号不同（可能是学号错误）
- 相似的学号或姓名（手动输入错误）

### 使用模糊匹配

```python
from core.deduplication import DeduplicationService

service = DeduplicationService(async_db)
result = await service.check_all(email_uid, student_id, assignment_name)

# 检查可能的重复
if result.possible_duplicates:
    print(f"发现 {len(result.possible_duplicates)} 个可能的重复:")
    for dup in result.possible_duplicates:
        print(f"  - ID: {dup.id}, 学号: {dup.student_id}, 姓名: {dup.name}")
        print(f"    相似度: {dup.match_score:.2f}, 关系: {dup.relation_type}")
```

### 查看可能的重复

在 UI 中，可能的重复提交会以缩进形式显示在主记录下方，并带有特殊标识：

1. **版本关系** (VERSION)
   - 精确匹配（学号+姓名+作业完全相同）
   - 显示为历史版本
   - 可以折叠/展开查看版本历史

2. **可能重复** (POSSIBLE_DUP)
   - 学号相同但姓名不同
   - 姓名相同但学号不同
   - 相似的学号或姓名
   - 显示为可能重复，需要人工确认

### 查看历史版本

```python
from core.deduplication.submission_group_manager import SubmissionGroupManager

group_mgr = SubmissionGroupManager(async_db)

# 获取主记录
primary = await group_mgr.get_primary_submission(submission_id)

# 获取所有子记录（版本）
children = await group_mgr.get_all_children(primary.id)

# 只获取版本关系
versions = await group_mgr.get_all_children(
    primary.id,
    relation_type=RelationType.VERSION
)

# 只获取可能重复
possible_dups = await group_mgr.get_all_children(
    primary.id,
    relation_type=RelationType.POSSIBLE_DUP
)
```

### 相似度评分

模糊匹配使用以下评分机制：

- **精确匹配**: 0.7 分（学号或姓名完全相同）
- **相似学号**: 0.4 分 + 相似度 × 0.5
- **相似姓名**: 0.4 分 + 相似度 × 0.5

阈值：
- 学号相似度阈值: 0.8
- 姓名相似度阈值: 0.6
- 最小重复分数: 0.3

### FuzzyMatcher API

```python
from core.deduplication.fuzzy_matcher import FuzzyMatcher

matcher = FuzzyMatcher(async_db)

# 查找可能的重复
duplicates = await matcher.find_possible_duplicates(
    student_id="S001",
    name="张三",
    assignment_name="作业1"
)

# 计算匹配分数
score = matcher.calculate_match_score(
    student_id_1="S001",
    name_1="张三",
    student_id_2="S002",
    name_2="张小三"
)

# 分类关系类型
relation = matcher.classify_relation(
    match_score=0.85,
    same_student_id=True,
    same_name=False
)
# 返回: RelationType.POSSIBLE_DUP
```

### UI 显示规则

1. **主记录** (is_primary=True)
   - 顶层显示，不缩进
   - 可以折叠/展开子记录

2. **子记录** (has parent_id)
   - 缩进显示在父记录下方
   - 根据关系类型显示不同标识：
     - VERSION: "v2", "v3" 等版本号
     - POSSIBLE_DUP: "可能重复" 标识

3. **折叠/展开**
   - 点击主记录的折叠按钮切换子记录显示
   - 默认状态可以配置
   - 支持批量操作（全部展开/折叠）

### 数据转换服务

DataTransformService 负责将数据库记录转换为 UI 可用的格式：

```python
from mail.data_transform_service import data_transform_service

# 转换单个记录
ui_data = await data_transform_service.transform_to_ui(submission)

# 批量转换
ui_list = await data_transform_service.transform_list(submissions)

# 构建树形结构
tree = await data_transform_service.build_tree(primary_id)
```

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
