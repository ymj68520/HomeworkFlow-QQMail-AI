# 附件验证系统设计文档

**日期**: 2026-05-11
**作者**: Claude Code
**状态**: 设计阶段

## 1. 概述

### 1.1 目标

在现有的QQ邮箱作业收发系统中添加统一的附件验证层，限制作业提交的可接受文件类型和大小，提高系统安全性和可维护性。

### 1.2 需求

| 需求项 | 描述 |
|--------|------|
| 文件类型限制 | 支持文档、图片、压缩文件类型，可由用户动态配置 |
| 单文件大小限制 | 最大 25MB |
| 总大小限制 | 单封邮件附件总大小最大 100MB |
| 拒绝策略 | 完全拒绝不符合规则的邮件（保持未读，不移动，不保存） |
| 可配置性 | 用户可通过GUI界面修改配置，无需重启应用 |
| 持久化 | 配置存储在数据库，重启不丢失 |

## 2. 架构设计

### 2.1 系统架构

```
外部配置层 (YAML)
    ↓
配置管理层 (AttachmentConfigManager)
    ↓
验证服务层 (AttachmentValidator)
    ↓
工作流集成层 (AssignmentWorkflow)
    ↓
数据持久化层 (AttachmentValidationRule)
```

### 2.2 组件说明

#### 2.2.1 外部配置层

**文件**: `config/attachment_presets.yaml`

预设分类配置文件，用户可编辑。包含：
- `categories`: 预设分类定义
- `default_enabled_categories`: 默认启用的分类
- `default_size_limits`: 默认大小限制

#### 2.2.2 配置管理层

**类**: `AttachmentConfigManager`

职责：
- 从YAML文件加载预设分类
- 管理数据库中的验证规则
- 提供配置缓存机制
- 支持配置热重载

#### 2.2.3 验证服务层

**类**: `AttachmentValidator`

职责：
- 执行附件验证逻辑
- 验证文件类型、单文件大小、总大小
- 返回详细的验证结果

#### 2.2.4 工作流集成层

**集成点**: `core/workflow.py::AssignmentWorkflow.process_new_email()`

在AI提取信息之前进行验证，早期拒绝不符合规则的邮件。

#### 2.2.5 数据持久化层

**模型**: `AttachmentValidationRule`

存储当前生效的验证规则到数据库。

## 3. 数据模型

### 3.1 AttachmentValidationRule

```python
class AttachmentValidationRule(Base):
    __tablename__ = 'attachment_validation_rules'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    rule_name = Column(String(50), unique=True, nullable=False)
    allowed_extensions = Column(Text, nullable=False)  # JSON: [".pdf", ".doc", ...]
    extension_categories = Column(Text)  # JSON: {"document": [".pdf", ...]}
    max_file_size_mb = Column(Float, nullable=False)
    max_total_size_mb = Column(Float, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
```

### 3.2 ValidationResult

```python
@dataclass
class ValidationResult:
    is_valid: bool
    reason: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)
```

## 4. 接口设计

### 4.1 AttachmentConfigManager

```python
class AttachmentConfigManager:
    def load_preset_categories(self) -> Dict[str, dict]:
        """从外部配置文件加载预设分类"""
        
    def get_preset_extensions(self, category_names: List[str]) -> List[str]:
        """根据分类名称获取扩展名列表"""
        
    async def get_current_rules(self) -> AttachmentValidationRule:
        """获取当前生效的规则（带缓存）"""
        
    async def update_rules(
        self,
        allowed_extensions: List[str],
        max_file_size_mb: float,
        max_total_size_mb: float
    ) -> bool:
        """更新规则（立即生效）"""
        
    def reload_presets(self):
        """重新加载预设配置"""
        
    def validate_presets_file(self) -> dict:
        """验证预设配置文件的格式是否正确"""
```

### 4.2 AttachmentValidator

```python
class AttachmentValidator:
    def __init__(self, config_manager: AttachmentConfigManager):
        self.config_mgr = config_manager
        
    async def validate_attachments(
        self,
        attachments: List[Dict]
    ) -> ValidationResult:
        """验证附件
        
        Args:
            attachments: 附件列表 [{'filename': 'a.pdf', 'content': b'...', 'size': 1024}, ...]
            
        Returns:
            ValidationResult
        """
```

## 5. 验证规则

### 5.1 文件类型验证

- 获取附件的文件扩展名
- 检查是否在 `allowed_extensions` 列表中
- 扩展名匹配不区分大小写

### 5.2 单文件大小验证

- 检查每个附件的 `size` 字段
- 必须 ≤ `max_file_size_mb`

### 5.3 总大小验证

- 计算所有附件的总大小
- 必须 ≤ `max_total_size_mb`

## 6. 集成点

### 6.1 工作流集成

在 `core/workflow.py::AssignmentWorkflow.process_new_email()` 中添加验证逻辑：

```python
async def process_new_email(self, email_uid: str) -> dict:
    # 1. 解析邮件
    email_data = self.parser.parse_email(email_uid)
    
    # 2. 检查是否有附件
    if not email_data['has_attachments']:
        ...
    
    # 3. 🆕 验证附件规则
    validation_result = await self.attachment_validator.validate_attachments(
        email_data['attachments']
    )
    
    if not validation_result.is_valid:
        # 保持未读，记录日志，返回
        self.db.log_email_action(
            email_uid=email_uid,
            action='attachment_rejected',
            folder='INBOX',
            details=validation_result.reason
        )
        return {
            'success': False,
            'action': 'rejected',
            'reason': validation_result.reason
        }
    
    # 4. 继续原有流程
    # ...
```

## 7. GUI界面

### 7.1 配置对话框

**文件**: `gui/attachment_config_dialog.py`

功能：
- 显示预设分类复选框（从YAML加载）
- 自定义扩展名编辑器
- 大小限制输入框
- 保存/应用/重置按钮

### 7.2 主窗口集成

在 `gui/main_window.py` 中添加菜单项：
- "设置" → "附件验证规则"

## 8. 错误处理

### 8.1 验证失败

当附件验证失败时：
- 邮件保持未读状态
- 记录拒绝日志到 `email_log` 表
- 不保存附件
- 不移动邮件
- 不发送确认邮件

### 8.2 配置文件错误

当YAML配置文件格式错误时：
- 记录错误日志
- 回退到内置默认配置
- 系统继续正常运行

## 9. 性能考虑

### 9.1 配置缓存

`AttachmentConfigManager` 使用内存缓存，缓存过期时间为1分钟。

### 9.2 早期验证

在AI提取之前进行验证，避免不必要的资源消耗。

## 10. 测试策略

### 10.1 单元测试

- `test_attachment_config_manager.py`: 配置管理器测试
- `test_attachment_validator.py`: 验证器测试

### 10.2 集成测试

- `test_attachment_validation_e2e.py`: 端到端测试

### 10.3 测试用例

| 场景 | 预期结果 |
|------|----------|
| 所有附件符合规则 | 验证通过，继续处理 |
| 有附件类型不符合 | 验证失败，邮件被拒绝 |
| 有附件超过单文件大小限制 | 验证失败，邮件被拒绝 |
| 附件总大小超过限制 | 验证失败，邮件被拒绝 |
| 无附件 | 不触发验证逻辑 |
| 配置文件不存在 | 使用内置默认配置 |
| 配置文件格式错误 | 使用内置默认配置，记录错误 |

## 11. 部署计划

### 11.1 数据库迁移

创建迁移脚本 `database/migrations/002_add_attachment_rules.py`

### 11.2 配置文件初始化

首次运行时，如果 `config/attachment_presets.yaml` 不存在，创建默认配置文件。

### 11.3 依赖项

新增依赖：
- `pyyaml`: YAML配置文件解析

## 12. 未来扩展

### 12.1 可能的增强

- 病毒扫描集成
- 文件内容验证（如PDF有效性）
- 用户级别的个性化规则
- 规则版本管理和回滚

## 13. 附录

### 13.1 默认配置

```yaml
categories:
  document:
    display_name: "文档类型"
    extensions: [.pdf, .doc, .docx, .xls, .xlsx, .ppt, .pptx, .txt]
  image:
    display_name: "图片类型"
    extensions: [.png, .jpg, .jpeg, .gif, .bmp, .webp]
  archive:
    display_name: "压缩文件"
    extensions: [.zip, .rar, .7z, .tar, .gz]

default_size_limits:
  max_file_size_mb: 25
  max_total_size_mb: 100
```

### 13.2 日志格式

验证失败日志示例：
```json
{
  "email_uid": "12345",
  "action": "attachment_rejected",
  "folder": "INBOX",
  "details": "不允许的文件类型: .exe (filename: virus.exe)"
}
```
